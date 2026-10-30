import json

from agent.benchmark import load_issues, run_benchmark, summarise, wrote_failing_test
from tests.conftest import MEDIAN_FIX, MEDIAN_TEST, WEAK_TEST, median_replies

# Changes nothing that matters, so the repo's own tests still pass but the hidden test fails.
COSMETIC_FIX = {
    "explanation": "Return the middle value.",
    "edits": [
        {
            "file": "shopkit/stats.py",
            "find": "    return ordered[middle]\n",
            "replace": "    return ordered[middle]  # the middle value\n",
        }
    ],
}


def test_correct_fix_is_solved_and_approved(make_deps, tmp_path):
    deps = make_deps(median_replies({"code": MEDIAN_TEST}, MEDIAN_FIX))
    [result] = run_benchmark([8], deps, tmp_path)

    assert result.solved and result.offered
    assert result.regression_test
    assert result.patch_attempts == 1
    assert deps.store.get_run(result.run_id)["status"] == "approved"
    # The hidden test ran against the patched repo.
    hidden = deps.sandbox.calls[-1]["changes"]
    assert "tests/test_hidden_issue_8.py" in hidden
    assert "shopkit/stats.py" in hidden

    saved = json.loads((tmp_path / "fake-model.json").read_text())
    assert saved["summary"]["solved"] == 1
    assert "| 8 | median is wrong" in (tmp_path / "fake-model.md").read_text()


def test_fix_that_only_passes_its_own_tests_is_rejected(make_deps, tmp_path):
    # No regression test reproduces the bug, so only the repo's own tests judge the fix.
    deps = make_deps(median_replies({"code": WEAK_TEST}, {"code": WEAK_TEST}, COSMETIC_FIX))
    [result] = run_benchmark([8], deps, tmp_path)

    assert result.offered and not result.solved
    assert not result.regression_test
    assert result.note.startswith("Hidden test failed")
    run = deps.store.get_run(result.run_id)
    assert run["status"] == "rejected"
    assert run["error"].startswith("Hidden test failed")

    summary = summarise([result])
    assert summary["review_precision"] == 0.0
    assert summary["offered_for_review"] == 1


def test_every_demo_issue_names_its_hidden_test(settings):
    issues = load_issues(settings.demo_issues)
    assert [i["number"] for i in issues] == list(range(1, len(issues) + 1))
    assert len(issues) == 18


def test_a_failing_test_counts_even_when_the_run_fails_later():
    def step(name, exit_code):
        return {"name": name, "output": {"result": {"exit_code": exit_code}}}

    assert wrote_failing_test([step("write_test", 0), step("write_test", 1)])
    # Passing on the unfixed code (0) or not running at all (2) does not show the bug.
    assert not wrote_failing_test([step("write_test", 0), step("write_test", 2)])
    assert not wrote_failing_test([step("run_tests", 1)])
