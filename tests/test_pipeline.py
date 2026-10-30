from agent.llm import InvalidReplyError
from agent.pipeline import execute_run
from agent.targets import resolve_target
from tests.conftest import MEDIAN_FIX, FakeLLM, median_replies

BAD_PATCH = {
    "explanation": "Guess.",
    "edits": [{"file": "shopkit/stats.py", "find": "return ordered[mid]", "replace": "x"}],
}


def run_demo(issue_number, llm, store, settings) -> dict:
    target = resolve_target("demo", None, settings)
    run_id = store.create_run(target.label, issue_number, llm.model)
    execute_run(run_id, issue_number, target, llm, store, settings)
    return store.get_run(run_id)


def test_suggests_a_patch_and_records_every_step(store, settings):
    run = run_demo(8, FakeLLM(median_replies(MEDIAN_FIX)), store, settings)
    assert run["status"] == "suggested"
    assert run["issue_title"] == "median is wrong for an even number of values"
    assert "+    if len(ordered) % 2 == 0:" in run["diff"]
    assert run["explanation"] == MEDIAN_FIX["explanation"]
    assert [s["name"] for s in run["steps"]] == [
        "fetch_issue", "prepare_workspace", "classify", "search_code", "choose_files",
        "propose_patch",
    ]  # fmt: skip
    assert run["steps"][3]["output"]["result"][0] == "shopkit/stats.py"
    # The demo repo itself is never modified.
    assert "return ordered[middle]\n" in (settings.demo_repo / "shopkit/stats.py").read_text()


def test_retries_with_the_error_shown_to_the_model(store, settings):
    llm = FakeLLM(median_replies(BAD_PATCH, InvalidReplyError("cut off"), MEDIAN_FIX))
    run = run_demo(8, llm, store, settings)
    assert run["status"] == "suggested"
    patch_steps = [s["status"] for s in run["steps"] if s["name"] == "propose_patch"]
    assert patch_steps == ["error", "error", "ok"]
    assert "was not found in shopkit/stats.py" in llm.prompts[3]
    assert "cut off" in llm.prompts[4]


def test_fails_after_the_last_attempt(store, settings):
    run = run_demo(8, FakeLLM(median_replies(BAD_PATCH, BAD_PATCH, BAD_PATCH)), store, settings)
    assert run["status"] == "failed"
    assert "after 3 attempts" in run["error"]
    assert run["finished_at"]


def test_questions_are_skipped(store, settings):
    llm = FakeLLM([{"kind": "question", "summary": "Asks how median works."}])
    run = run_demo(8, llm, store, settings)
    assert run["status"] == "skipped"
    assert run["diff"] == ""


def test_an_invalid_file_choice_falls_back_to_the_best_search_hit(store, settings):
    replies = median_replies(MEDIAN_FIX)
    replies[1] = {"files": ["../../agent/config.py"], "reason": "?"}
    run = run_demo(8, FakeLLM(replies), store, settings)
    assert run["status"] == "suggested"
    assert run["steps"][4]["output"]["files"] == ["shopkit/stats.py"]


def test_unknown_issue_fails_the_run(store, settings):
    run = run_demo(99, FakeLLM([]), store, settings)
    assert run["status"] == "failed"
    assert "no demo issue #99" in run["error"]
