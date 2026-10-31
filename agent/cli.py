"""Command line: list issues, run the agent on one, and approve or reject its patch.

python -m agent.cli issues --demo
python -m agent.cli run --demo 3
python -m agent.cli run owner/name 12
python -m agent.cli approve 5
python -m agent.cli reject 5 --comment "Wrong file"
"""

import argparse
import sys

from agent.github_client import GitHubError
from agent.graph import resume_run, start_run
from agent.main import get_deps
from agent.targets import resolve_target


def show(run: dict) -> None:
    for step in run["steps"]:
        print(f"  {step['name']:<18} {step['status']:<6} {step['duration_ms'] / 1000:6.1f}s")
    print(f"\nStatus: {run['status']}")
    for label, key in [("Error", "error"), ("Pull request", "pr_url")]:
        if run[key]:
            print(f"{label}: {run[key]}")
    if run["explanation"]:
        print(f"\n{run['explanation']}")
    if run["diff"]:
        print(f"\n{run['diff']}")
    if run["test_output"]:
        print(f"Tests:\n{run['test_output']}")
    if run["status"] == "awaiting_approval":
        print(f"\nApprove:  python -m agent.cli approve {run['id']}")
        print(f"Reject:   python -m agent.cli reject {run['id']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    issues = commands.add_parser("issues", help="List open issues")
    run = commands.add_parser("run", help="Run the agent on an issue")
    for command in (issues, run):
        group = command.add_mutually_exclusive_group(required=True)
        group.add_argument("repo", nargs="?", help="GitHub repository as owner/name")
        group.add_argument("--demo", action="store_true", help="Use the bundled demo repo")
    run.add_argument("number", type=int, help="Issue number")
    for name in ("approve", "reject"):
        review = commands.add_parser(name, help=f"{name.title()} a patch awaiting approval")
        review.add_argument("run_id", type=int)
        review.add_argument("--comment", default="")
    args = parser.parse_args(argv)

    deps = get_deps()
    if args.command == "issues":
        try:
            target = resolve_target("demo" if args.demo else "github", args.repo, deps.settings)
            issues = target.issues.list_open()
        except (ValueError, LookupError, GitHubError) as exc:
            print(f"Cannot list issues: {exc}")
            return 1
        for issue in issues:
            print(f"#{issue.number:<4} {issue.title}")
        return 0

    if args.command == "run":
        source = "demo" if args.demo else "github"
        run_id = deps.store.create_run(args.repo or "demo", args.number, deps.llm.model)
        print(f"Run {run_id}: working on issue #{args.number} with {deps.llm.model}.")
        print("This takes a few minutes on a CPU.\n")
        start_run(run_id, source, args.repo, args.number, deps)
    else:
        run_id = args.run_id
        current = deps.store.get_run(run_id)
        # The same atomic claim as the API, so the CLI and the dashboard can't both resume it.
        if current is None or not deps.store.claim_for_review(run_id):
            status = current["status"] if current else "missing"
            print(f"Run {run_id} is {status}, not awaiting approval.")
            return 1
        resume_run(run_id, args.command == "approve", args.comment, deps)

    result = deps.store.get_run(run_id)
    show(result)
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
