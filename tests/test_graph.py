import json
import subprocess

import httpx

from agent import graph as graph_module
from agent.github_client import GitHubClient
from agent.graph import resume_run, start_run
from agent.issues import Issue
from agent.llm import InvalidReplyError
from agent.targets import Target
from tests.conftest import MEDIAN_FIX, MEDIAN_TEST, WEAK_TEST, WRONG_FIX, median_replies


def start(deps, issue_number=8, source="demo", repo=None) -> dict:
    run_id = deps.store.create_run(repo or "demo", issue_number, deps.llm.model)
    start_run(run_id, source, repo, issue_number, deps)
    return deps.store.get_run(run_id)


def step_names(run) -> list[str]:
    return [s["name"] for s in run["steps"]]


def test_passing_patch_waits_for_approval_then_is_saved(make_deps, settings):
    deps = make_deps(median_replies({"code": MEDIAN_TEST}, MEDIAN_FIX))
    run = start(deps)

    assert run["status"] == "awaiting_approval"
    assert step_names(run) == [
        "fetch_issue", "prepare_workspace", "classify", "search_code", "choose_files",
        "write_test", "propose_patch", "run_tests",
    ]  # fmt: skip
    assert "+++ b/tests/test_agent_issue_8.py" in run["diff"]
    assert "+        return (ordered[middle - 1] + ordered[middle]) / 2" in run["diff"]
    assert run["regression_test"] == MEDIAN_TEST
    assert "passed" in run["test_output"]
    # The regression test was checked on the unchanged code first, and failed there.
    first = deps.sandbox.calls[0]
    assert list(first["changes"]) == ["tests/test_agent_issue_8.py"]

    resume_run(run["id"], True, "", deps)
    run = deps.store.get_run(run["id"])
    assert run["status"] == "approved"
    assert step_names(run)[-2:] == ["human_review", "save_patch"]
    assert (settings.patches_dir / f"run-{run['id']}.diff").read_text() == run["diff"]


def test_rejected_patch_is_not_applied(make_deps, settings):
    deps = make_deps(median_replies({"code": MEDIAN_TEST}, MEDIAN_FIX))
    run = start(deps)
    resume_run(run["id"], False, "Wrong approach", deps)
    run = deps.store.get_run(run["id"])
    assert run["status"] == "rejected"
    assert run["error"] == "Wrong approach"
    assert not settings.patches_dir.exists()


def test_failing_tests_are_shown_to_the_model_for_a_retry(make_deps):
    deps = make_deps(median_replies({"code": MEDIAN_TEST}, WRONG_FIX, MEDIAN_FIX))
    run = start(deps)
    assert run["status"] == "awaiting_approval"
    results = [s["output"]["passed"] for s in run["steps"] if s["name"] == "run_tests"]
    assert results == [False, True]
    retry_prompt = deps.llm.prompts[-1]
    assert "The tests failed with your change" in retry_prompt
    assert "test_median_of_even_count" in retry_prompt


def test_a_test_that_passes_today_is_rejected(make_deps):
    deps = make_deps(median_replies({"code": WEAK_TEST}, {"code": MEDIAN_TEST}, MEDIAN_FIX))
    run = start(deps)
    assert run["regression_test"] == MEDIAN_TEST
    assert "does not show the bug" in deps.llm.prompts[3]


def test_without_a_reproducing_test_the_repo_tests_still_judge_the_patch(make_deps):
    broken = {"code": "def test_broken(:\n"}
    deps = make_deps(median_replies({"code": WEAK_TEST}, broken, WRONG_FIX))
    deps.settings.max_patch_attempts = 1
    run = start(deps)
    # The repo's own test median([3, 1, 2]) == 2 catches the wrong fix.
    assert run["status"] == "failed"
    assert "No patch passed after 1 attempts" in run["error"]
    assert "middle = len(ordered) // 2 - 1" in run["diff"]
    assert run["regression_test"] == ""


def test_invalid_replies_use_up_attempts(make_deps):
    replies = median_replies({"code": MEDIAN_TEST}, *[InvalidReplyError("cut off")] * 3)
    run = start(make_deps(replies))
    assert run["status"] == "failed"
    assert "cut off" in run["error"]


def test_questions_are_skipped(make_deps):
    deps = make_deps([{"kind": "question", "summary": "Asks how median works."}])
    run = start(deps)
    assert run["status"] == "skipped"
    assert run["explanation"] == "Asks how median works."


def test_unknown_issue_fails_the_run(make_deps):
    run = start(make_deps([]), issue_number=99)
    assert run["status"] == "failed"
    assert "no demo issue #99" in run["error"]


def test_approval_on_github_opens_a_draft_pr(make_deps, settings, tmp_path, monkeypatch):
    # A local git copy of the demo repo stands in for the clone of the GitHub repository.
    repo_dir = tmp_path / "clone"
    subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)
    from agent.sandbox import copy_repo

    copy_repo(settings.demo_repo, repo_dir / "x", {})
    for item in (repo_dir / "x").iterdir():
        item.rename(repo_dir / item.name)
    (repo_dir / "x").rmdir()
    git = ["git", "-C", str(repo_dir), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    head = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout

    class Issues:
        def get(self, number):
            return Issue(8, "median is wrong for an even number of values", "median([1,2,3,4])")

    monkeypatch.setattr(
        graph_module,
        "resolve_target",
        lambda *args: Target("o/r", Issues(), lambda: repo_dir),
    )
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path, request.content))
        if request.method == "GET" and request.url.path == "/repos/o/r":
            return httpx.Response(200, json={"default_branch": "main"})
        if request.method == "GET":  # contents of a file on the new branch
            exists = request.url.path.endswith("stats.py")
            return httpx.Response(200, json={"sha": "abc"}) if exists else httpx.Response(404)
        if request.url.path.endswith("/pulls"):
            return httpx.Response(201, json={"html_url": "https://github.com/o/r/pull/1"})
        return httpx.Response(201, json={})

    github = GitHubClient(token="t", transport=httpx.MockTransport(handler))
    deps = make_deps(median_replies({"code": MEDIAN_TEST}, MEDIAN_FIX), github=github)
    run = start(deps, source="github", repo="o/r")
    assert run["status"] == "awaiting_approval"
    assert requests == []  # nothing is sent to GitHub before approval

    resume_run(run["id"], True, "", deps)
    run = deps.store.get_run(run["id"])
    assert run["status"] == "pr_opened"
    assert run["pr_url"] == "https://github.com/o/r/pull/1"

    ref = json.loads(next(c for m, p, c in requests if p.endswith("/git/refs")))
    assert ref == {"ref": f"refs/heads/agent/issue-8-run-{run['id']}", "sha": head.strip()}
    puts = {p: json.loads(c) for m, p, c in requests if m == "PUT"}
    assert puts["/repos/o/r/contents/shopkit/stats.py"]["sha"] == "abc"
    assert "sha" not in puts["/repos/o/r/contents/tests/test_agent_issue_8.py"]
    pr = json.loads(next(c for m, p, c in requests if p.endswith("/pulls")))
    assert pr["draft"] is True and pr["base"] == "main"
    assert pr["body"].startswith("Fixes #8.")


def test_resuming_never_marks_the_run_awaiting_approval_again(make_deps):
    # A reviewer's page polling during the resume must not see the decision undone.
    deps = make_deps(median_replies({"code": MEDIAN_TEST}, MEDIAN_FIX))
    run = start(deps)
    statuses = []
    update_run = deps.store.update_run

    def record(run_id, **fields):
        if "status" in fields:
            statuses.append(fields["status"])
        update_run(run_id, **fields)

    deps.store.update_run = record
    resume_run(run["id"], True, "", deps)
    assert statuses == ["running", "approved"]
