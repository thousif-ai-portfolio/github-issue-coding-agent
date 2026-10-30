"""Measures the agent on the demo repo.

Each issue gets a normal run. When a run reaches review, its patch is checked in the
sandbox against the issue's hidden test, which the agent never saw, and the benchmark then
approves or rejects it the way a reviewer would. So a run counts as solved only if the
hidden test passes, not merely the tests the agent wrote for itself.

    python -m agent.benchmark              # every demo issue, about 1 hour on a laptop CPU
    python -m agent.benchmark --issues 1 8
"""

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from agent.graph import Deps, pending_changes, resume_run, start_run
from agent.sandbox import TestResult

RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "results"


@dataclass
class IssueResult:
    number: int
    title: str
    run_id: int
    status: str  # the run's status after review: approved, rejected, failed or skipped
    offered: bool  # reached review: the agent's own tests passed
    solved: bool  # the hidden test passed too
    patch_attempts: int
    regression_test: bool  # the agent wrote a test that failed before its fix
    agent_seconds: float
    note: str = ""


def load_issues(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def hidden_check(issue: dict, changes: dict[str, str], deps: Deps) -> TestResult:
    """Runs the repo's tests plus the issue's hidden test on the patched repo."""
    hidden = deps.settings.demo_issues.parent / "hidden_tests" / issue["hidden_test"]
    # Named test_*.py so pytest collects it.
    path = f"tests/test_hidden_{issue['hidden_test'].removeprefix('test_')}"
    return deps.sandbox.run_tests(
        deps.settings.demo_repo, {**changes, path: hidden.read_text(encoding="utf-8")}
    )


def last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


def wrote_failing_test(steps: list[dict]) -> bool:
    """Whether a write_test step produced a test that failed on the unfixed code (pytest
    exit code 1). Read from the trace, because a run only saves the test once it
    reaches review."""
    return any(
        s["name"] == "write_test" and s["output"].get("result", {}).get("exit_code") == 1
        for s in steps
    )


def score_issue(issue: dict, deps: Deps) -> IssueResult:
    run_id = deps.store.create_run("demo", issue["number"], deps.llm.model)
    start_run(run_id, "demo", None, issue["number"], deps)
    run = deps.store.get_run(run_id)

    offered = run["status"] == "awaiting_approval"
    solved, note = False, ""
    if offered:
        result = hidden_check(issue, pending_changes(run_id, deps), deps)
        solved = result.passed
        note = "" if solved else f"Hidden test failed: {last_line(result.output)}"
        resume_run(run_id, solved, "" if solved else note, deps)
        run = deps.store.get_run(run_id)
    elif run["status"] == "failed":
        note = last_line(run["error"])
    elif run["status"] == "skipped":
        note = "Classified as not a bug."

    steps = run["steps"]
    return IssueResult(
        number=issue["number"],
        title=issue["title"],
        run_id=run_id,
        status=run["status"],
        offered=offered,
        solved=solved,
        patch_attempts=sum(1 for s in steps if s["name"] == "propose_patch"),
        regression_test=wrote_failing_test(steps),
        agent_seconds=round(
            sum(s["duration_ms"] for s in steps if s["name"] != "human_review") / 1000, 1
        ),
        note=note,
    )


def summarise(results: list[IssueResult]) -> dict:
    total = len(results)
    solved = [r for r in results if r.solved]
    offered = [r for r in results if r.offered]
    return {
        "issues": total,
        "solved": len(solved),
        "solve_rate": round(len(solved) / total, 3) if total else 0.0,
        "offered_for_review": len(offered),
        # When the agent's own tests passed, how often the hidden test agreed.
        "review_precision": round(len(solved) / len(offered), 3) if offered else 0.0,
        "solved_first_attempt": sum(1 for r in solved if r.patch_attempts == 1),
        "solved_after_retry": sum(1 for r in solved if r.patch_attempts > 1),
        "regression_tests_written": sum(1 for r in results if r.regression_test),
        "median_agent_seconds": statistics.median(r.agent_seconds for r in results)
        if results
        else 0.0,
        "total_agent_minutes": round(sum(r.agent_seconds for r in results) / 60, 1),
    }


def to_markdown(results: list[IssueResult], summary: dict, model: str) -> str:
    s = summary
    lines = [
        f"# Benchmark: {model}",
        "",
        f"**Solved {s['solved']} of {s['issues']}** ({s['solve_rate']:.0%}), judged by hidden "
        f"tests the agent never saw.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Solved | {s['solved']} / {s['issues']} |",
        f"| Offered for review (agent's own tests passed) | {s['offered_for_review']} |",
        f"| Of those, also passed the hidden test | {s['review_precision']:.0%} |",
        f"| Solved on the first attempt / after a retry | {s['solved_first_attempt']} / "
        f"{s['solved_after_retry']} |",
        f"| Wrote a regression test that failed before the fix | "
        f"{s['regression_tests_written']} / {s['issues']} |",
        f"| Median agent time per issue | {s['median_agent_seconds']:.0f} s |",
        f"| Total agent time | {s['total_agent_minutes']} min |",
        "",
        "| # | Issue | Result | Attempts | Regression test | Time | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        result = "solved" if r.solved else ("wrong fix" if r.offered else r.status)
        note = r.note.replace("|", "\\|")
        lines.append(
            f"| {r.number} | {r.title} | {result} | {r.patch_attempts} | "
            f"{'yes' if r.regression_test else 'no'} | {r.agent_seconds:.0f} s | {note} |"
        )
    return "\n".join(lines) + "\n"


def save(results: list[IssueResult], model: str, out_dir: Path) -> Path:
    summary = summarise(results)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9.]+", "-", model).strip("-")
    payload = {"model": model, "summary": summary, "results": [asdict(r) for r in results]}
    (out_dir / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown = out_dir / f"{name}.md"
    markdown.write_text(to_markdown(results, summary, model), encoding="utf-8")
    return markdown


def run_benchmark(numbers: list[int] | None, deps: Deps, out_dir: Path = RESULTS_DIR) -> list:
    issues = load_issues(deps.settings.demo_issues)
    if numbers:
        issues = [i for i in issues if i["number"] in numbers]
    results: list[IssueResult] = []
    for issue in issues:
        start = time.perf_counter()
        print(f"#{issue['number']:<3} {issue['title'][:55]:<55} ", end="", flush=True)
        result = score_issue(issue, deps)
        results.append(result)
        # Saved after every issue, so an interrupted benchmark keeps what it measured.
        save(results, deps.llm.model, out_dir)
        verdict = "SOLVED" if result.solved else ("wrong fix" if result.offered else result.status)
        print(f"{verdict:<10} {time.perf_counter() - start:5.0f} s  run {result.run_id}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--issues", type=int, nargs="*", help="Only these issue numbers")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    from agent.main import get_deps

    deps = get_deps()
    results = run_benchmark(args.issues, deps, args.out)
    summary = summarise(results)
    print(
        f"\nSolved {summary['solved']} of {summary['issues']}. Results in {args.out.as_posix()}/."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
