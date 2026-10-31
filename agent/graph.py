"""The agent as a LangGraph state machine.

    fetch_issue -> prepare_workspace -> classify --(question)--> skipped
        -> search_code -> choose_files -> write_test
        -> propose_patch <-> run_tests      (retry with the error, up to 3 attempts)
        -> offer_for_review -> await_approval --(rejected)--> rejected
        -> open_pr

The graph pauses at await_approval until a person approves or rejects the patch. Its state
is saved to SQLite after every step, so a paused run survives a restart and resumes from
where it stopped. All code access goes through the MCP tool server.
"""

import logging
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent.config import Settings
from agent.edits import EditError, apply_edits, check_syntax, make_diff
from agent.git_ops import head_commit
from agent.github_client import GitHubClient
from agent.issues import Issue
from agent.llm import LLM, InvalidReplyError
from agent.mcp_server import build_server
from agent.prompts import (
    SYSTEM,
    choose_files_prompt,
    classify_prompt,
    patch_prompt,
    test_prompt,
)
from agent.sandbox import Sandbox
from agent.schemas import Classification, FileChoice, PatchProposal, TestProposal
from agent.store import Store, Trace, now
from agent.targets import resolve_target
from agent.tools import ToolClient
from agent.workspace import is_test_file

log = logging.getLogger(__name__)


class AgentError(RuntimeError):
    pass


class RunState(TypedDict, total=False):
    run_id: int
    source: str
    repo: str | None
    issue_number: int
    issue: dict
    root: str
    classification: dict
    candidates: list[str]
    files: list[str]
    regression_test: dict | None  # {"path", "code"}, or None if no test reproduced the bug
    attempt: int
    feedback: str
    patch: dict | None  # {"explanation", "changes", "diff"}
    test_result: dict | None
    decision: dict


@dataclass
class Deps:
    llm: LLM
    sandbox: Sandbox
    store: Store
    settings: Settings
    github: GitHubClient


def _normalise_path(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./")


def _test_path(root: Path, issue_number: int) -> str:
    folder = "tests/" if (root / "tests").is_dir() else ""
    return f"{folder}test_agent_issue_{issue_number}.py"


class Agent:
    """The graph's nodes. Each reads the state, does one thing and returns what changed."""

    def __init__(self, deps: Deps) -> None:
        self.deps = deps
        self.settings = deps.settings

    # --- helpers ---

    def _trace(self, state: RunState) -> Trace:
        return Trace(self.deps.store, state["run_id"])

    def _issue(self, state: RunState) -> Issue:
        return Issue(**state["issue"])

    def _root(self, state: RunState) -> Path:
        return Path(state["root"])

    def _tools(self, state: RunState) -> ToolClient:
        root = self._root(state)
        return ToolClient(build_server(root, self.deps.sandbox, self.settings))

    def _target(self, state: RunState):
        return resolve_target(state["source"], state.get("repo"), self.settings, self.deps.github)

    def _finish(self, state: RunState, status: str, **fields: str) -> dict:
        self.deps.store.update_run(state["run_id"], status=status, finished_at=now(), **fields)
        return {}

    # --- nodes ---

    def fetch_issue(self, state: RunState) -> dict:
        number = state["issue_number"]
        issue = self._trace(state).step(
            "fetch_issue", {"number": number}, partial(self._target(state).issues.get, number)
        )
        self.deps.store.update_run(state["run_id"], issue_title=issue.title)
        return {"issue": asdict(issue)}

    def prepare_workspace(self, state: RunState) -> dict:
        target = self._target(state)
        root = self._trace(state).step(
            "prepare_workspace", {"repo": target.label}, partial(target.workspace, state["run_id"])
        )
        return {"root": str(root)}

    def classify(self, state: RunState) -> dict:
        prompt = classify_prompt(self._issue(state))

        def classify() -> Classification:
            try:
                return self.deps.llm.complete(SYSTEM, prompt, Classification)
            except InvalidReplyError:
                # Treat it as a bug: the tests still decide whether a fix is right.
                return Classification(kind="bug", summary="The model's reply could not be read.")

        result = self._trace(state).step("classify", {"prompt": prompt}, classify)
        return {"classification": result.model_dump()}

    def search_code(self, state: RunState) -> dict:
        issue = self._issue(state)
        query = f"{issue.title}\n{issue.body}"
        candidates = self._trace(state).step(
            "search_code",
            {"tool": "search_code", "query": query},
            partial(self._tools(state).call, "search_code", query=query),
        )
        if not candidates:
            raise AgentError("No source file mentions anything named in the issue.")
        return {"candidates": candidates}

    def choose_files(self, state: RunState) -> dict:
        candidates = state["candidates"]
        prompt = choose_files_prompt(
            self._issue(state), self._root(state), candidates, self.settings.max_files
        )

        def choose() -> FileChoice:
            try:
                choice = self.deps.llm.complete(SYSTEM, prompt, FileChoice)
            except InvalidReplyError:
                choice = FileChoice(files=[], reason="The model's reply could not be read.")
            files = [f for f in map(_normalise_path, choice.files) if f in candidates]
            # Fall back to the best search hit rather than failing on a bad choice.
            files = list(dict.fromkeys(files))[: self.settings.max_files] or candidates[:1]
            return FileChoice(files=files, reason=choice.reason)

        choice = self._trace(state).step(
            "choose_files", {"prompt": prompt, "candidates": candidates}, choose
        )
        return {"files": choice.files}

    def write_test(self, state: RunState) -> dict:
        """Asks for a test that fails on the current code. Such a test shows the model
        understood the bug, and gives the patch a concrete target to pass."""
        root, issue, tools = self._root(state), self._issue(state), self._tools(state)
        path = _test_path(root, issue.number)
        existing = [f for f in tools.call("list_files") if is_test_file(f)]
        example = tools.call("read_source", path=existing[0]) if existing else ""
        feedback = ""
        for attempt in range(1, self.settings.max_test_attempts + 1):
            prompt = test_prompt(
                issue, root, state["files"], path, example, self.settings.max_file_chars, feedback
            )

            def attempt_test(prompt: str = prompt) -> dict:
                code = self.deps.llm.complete(SYSTEM, prompt, TestProposal).code
                check_syntax(path, code)
                result = tools.call("run_tests", changes={path: code}, tests=[path])
                return {"code": code, "result": result}

            try:
                outcome = self._trace(state).step(
                    "write_test", {"attempt": attempt, "prompt": prompt}, attempt_test
                )
            except (EditError, InvalidReplyError) as exc:
                feedback = str(exc)
                continue
            result = outcome["result"]
            if result["exit_code"] == 1:
                return {"regression_test": {"path": path, "code": outcome["code"]}}
            feedback = (
                "It passes on the current code, so it does not show the bug."
                if result["passed"]
                else f"It could not run:\n{result['output']}"
            )
        # The patch is then checked by the repository's own tests only.
        return {"regression_test": None}

    def propose_patch(self, state: RunState) -> dict:
        attempt = state.get("attempt", 0) + 1
        root, files = self._root(state), state["files"]
        test = state.get("regression_test")
        prompt = patch_prompt(
            self._issue(state),
            root,
            files,
            self.settings.max_file_chars,
            test["code"] if test else "",
            state.get("feedback", ""),
        )

        def propose() -> dict:
            proposal = self.deps.llm.complete(SYSTEM, prompt, PatchProposal)
            for edit in proposal.edits:
                edit.file = _normalise_path(edit.file)
            changes = apply_edits(root, proposal.edits, files)
            if test:
                changes[test["path"]] = test["code"]
            return {
                "explanation": proposal.explanation,
                "changes": changes,
                "diff": make_diff(root, changes),
            }

        try:
            patch = self._trace(state).step(
                "propose_patch", {"attempt": attempt, "prompt": prompt}, propose
            )
        except (EditError, InvalidReplyError) as exc:
            return {"attempt": attempt, "patch": None, "feedback": str(exc)}
        return {"attempt": attempt, "patch": patch, "feedback": ""}

    def run_tests(self, state: RunState) -> dict:
        changes = state["patch"]["changes"]
        result = self._trace(state).step(
            "run_tests",
            {"tool": "run_tests", "files": sorted(changes)},
            partial(self._tools(state).call, "run_tests", changes=changes),
        )
        feedback = (
            "" if result["passed"] else f"The tests failed with your change:\n{result['output']}"
        )
        return {"test_result": result, "feedback": feedback}

    def offer_for_review(self, state: RunState) -> dict:
        """Saves the patch on the run for a reviewer to read. A step of its own because
        await_approval runs again from the top when it resumes, and marking the run
        awaiting_approval then would briefly undo the reviewer's decision."""
        patch, result = state["patch"], state["test_result"]
        self.deps.store.update_run(
            state["run_id"],
            status="awaiting_approval",
            explanation=patch["explanation"],
            diff=patch["diff"],
            test_output=result["output"],
            regression_test=(state.get("regression_test") or {}).get("code", ""),
        )
        return {}

    def await_approval(self, state: RunState) -> dict:
        # Runs again on resume, so everything before interrupt() must be safe to repeat.
        decision = interrupt({"run_id": state["run_id"], "diff": state["patch"]["diff"]})
        self._trace(state).step("human_review", {}, lambda: decision)
        return {"decision": decision}

    def open_pr(self, state: RunState) -> dict:
        issue, patch, run_id = self._issue(state), state["patch"], state["run_id"]
        if state["source"] == "demo":
            # The demo repo has no GitHub repository, so the approved patch is saved instead.
            path = self.settings.patches_dir / f"run-{run_id}.diff"
            self._trace(state).step(
                "save_patch", {"path": path.as_posix()}, partial(_write, path, patch["diff"])
            )
            return self._finish(state, "approved")
        output = state["test_result"]["output"].replace("```", "` ` `")
        body = (
            f"Fixes #{issue.number}.\n\n{patch['explanation']}\n\n"
            f"Proposed by the issue coding agent and approved by a reviewer. The tests "
            f"passed in an isolated container:\n\n```\n{output}\n```"
        )
        root, branch = self._root(state), f"agent/issue-{issue.number}-run-{run_id}"
        files = {
            path: _line_endings_like(root / path, text) for path, text in patch["changes"].items()
        }
        url = self._trace(state).step(
            "open_pr",
            {"branch": branch},
            partial(
                self.deps.github.open_draft_pr,
                state["repo"],
                head_commit(root),
                branch,
                files,
                f"Fix #{issue.number}: {issue.title}",
                body,
            ),
        )
        return self._finish(state, "pr_opened", pr_url=url)

    def skipped(self, state: RunState) -> dict:
        return self._finish(state, "skipped", explanation=state["classification"]["summary"])

    def rejected(self, state: RunState) -> dict:
        return self._finish(state, "rejected", error=state["decision"].get("comment", ""))

    def failed(self, state: RunState) -> dict:
        last = state.get("feedback", "")
        return self._finish(
            state,
            "failed",
            error=f"No patch passed after {state.get('attempt', 0)} attempts. Last problem: {last}",
            diff=(state.get("patch") or {}).get("diff", ""),
        )

    # --- routing ---

    def after_classify(self, state: RunState) -> str:
        return "search_code" if state["classification"]["kind"] in ("bug", "feature") else "skipped"

    def after_propose(self, state: RunState) -> str:
        if state.get("patch"):
            return "run_tests"
        return self._retry_or_fail(state)

    def after_tests(self, state: RunState) -> str:
        if state["test_result"]["passed"]:
            return "offer_for_review"
        return self._retry_or_fail(state)

    def _retry_or_fail(self, state: RunState) -> str:
        return "propose_patch" if state["attempt"] < self.settings.max_patch_attempts else "failed"

    def after_review(self, state: RunState) -> str:
        return "open_pr" if state["decision"].get("approved") else "rejected"


def _line_endings_like(original: Path, text: str) -> str:
    """The agent works with LF; a file that used CRLF gets CRLF back, so its PR diff shows
    only the lines that changed."""
    if original.is_file() and b"\r\n" in original.read_bytes():
        return text.replace("\r\n", "\n").replace("\n", "\r\n")
    return text


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    # LF endings even on Windows, so the saved patch applies with git.
    path.write_text(text, encoding="utf-8", newline="\n")
    return path.as_posix()


def build_graph(deps: Deps, checkpointer) -> Any:
    agent = Agent(deps)
    graph = StateGraph(RunState)
    steps: dict[str, Callable] = {
        "fetch_issue": agent.fetch_issue,
        "prepare_workspace": agent.prepare_workspace,
        "classify": agent.classify,
        "search_code": agent.search_code,
        "choose_files": agent.choose_files,
        "write_test": agent.write_test,
        "propose_patch": agent.propose_patch,
        "run_tests": agent.run_tests,
        "offer_for_review": agent.offer_for_review,
        "await_approval": agent.await_approval,
        "open_pr": agent.open_pr,
        "skipped": agent.skipped,
        "rejected": agent.rejected,
        "failed": agent.failed,
    }
    for name, step in steps.items():
        graph.add_node(name, step)
    for a, b in [
        (START, "fetch_issue"),
        ("fetch_issue", "prepare_workspace"),
        ("prepare_workspace", "classify"),
        ("search_code", "choose_files"),
        ("choose_files", "write_test"),
        ("write_test", "propose_patch"),
        ("offer_for_review", "await_approval"),
        ("open_pr", END),
        ("skipped", END),
        ("rejected", END),
        ("failed", END),
    ]:
        graph.add_edge(a, b)
    graph.add_conditional_edges("classify", agent.after_classify, ["search_code", "skipped"])
    graph.add_conditional_edges(
        "propose_patch", agent.after_propose, ["run_tests", "propose_patch", "failed"]
    )
    graph.add_conditional_edges(
        "run_tests", agent.after_tests, ["offer_for_review", "propose_patch", "failed"]
    )
    graph.add_conditional_edges("await_approval", agent.after_review, ["open_pr", "rejected"])
    return graph.compile(checkpointer=checkpointer)


def _invoke(deps: Deps, run_id: int, payload: Any) -> None:
    """Runs the graph until it finishes or pauses for approval. Errors are saved on the
    run, not raised, because this runs as a background task with nobody to catch them."""
    try:
        deps.settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(deps.settings.checkpoint_path, check_same_thread=False)
        with closing(conn):
            graph = build_graph(deps, SqliteSaver(conn))
            graph.invoke(payload, {"configurable": {"thread_id": f"run-{run_id}"}})
    except Exception as exc:
        log.exception("Run %s failed", run_id)
        deps.store.update_run(run_id, status="failed", error=str(exc), finished_at=now())


def start_run(run_id: int, source: str, repo: str | None, issue_number: int, deps: Deps) -> None:
    state: RunState = {
        "run_id": run_id,
        "source": source,
        "repo": repo,
        "issue_number": issue_number,
        "attempt": 0,
        "feedback": "",
    }
    _invoke(deps, run_id, state)


def pending_changes(run_id: int, deps: Deps) -> dict[str, str]:
    """The files a paused run's patch would change ({path: new content}), read from its
    checkpoint. Empty if the run has no patch."""
    with closing(sqlite3.connect(deps.settings.checkpoint_path, check_same_thread=False)) as conn:
        graph = build_graph(deps, SqliteSaver(conn))
        state = graph.get_state({"configurable": {"thread_id": f"run-{run_id}"}}).values
    return dict((state.get("patch") or {}).get("changes") or {})


def resume_run(run_id: int, approved: bool, comment: str, deps: Deps) -> None:
    deps.store.update_run(run_id, status="running")
    _invoke(deps, run_id, Command(resume={"approved": approved, "comment": comment}))
