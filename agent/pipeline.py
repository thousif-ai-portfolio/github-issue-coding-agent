"""The agent's steps for one issue.

Week 1 stops at a suggested patch: nothing is executed and nothing is pushed. Week 2 moves
these steps into a LangGraph graph and adds sandboxed tests and human approval.
"""

import logging
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from pydantic import BaseModel

from agent.config import Settings
from agent.edits import EditError, apply_edits, make_diff
from agent.issues import Issue
from agent.llm import LLM, InvalidReplyError
from agent.schemas import Classification, Edit, FileChoice, PatchProposal
from agent.store import Store, Trace, now
from agent.targets import Target
from agent.workspace import issue_words, outline, rank_files, read_file

log = logging.getLogger(__name__)

SYSTEM = (
    "You are a careful software engineer who fixes GitHub issues with the smallest correct "
    "change. Reply only with JSON in the requested shape."
)
# Issue text is written by anyone; the cap keeps a huge issue from filling the prompt.
MAX_ISSUE_CHARS = 4000


class AgentError(RuntimeError):
    pass


class Patch(BaseModel):
    explanation: str
    edits: list[Edit]
    diff: str


@dataclass(frozen=True)
class Suggestion:
    status: str  # "suggested", or "skipped" when the issue does not ask for a code change
    classification: Classification
    files: list[str] = field(default_factory=list)
    explanation: str = ""
    diff: str = ""


def format_issue(issue: Issue) -> str:
    return f"Issue #{issue.number}: {issue.title}\n\n{issue.body[:MAX_ISSUE_CHARS]}"


def classify_prompt(issue: Issue) -> str:
    return (
        f"Classify this GitHub issue.\n\n{format_issue(issue)}\n\n"
        "kind: 'bug' if something is broken, 'feature' if it asks for new behaviour, "
        "'question' or 'other' otherwise. summary: one sentence saying what must change."
    )


def choose_files_prompt(issue: Issue, root: Path, candidates: list[str], max_files: int) -> str:
    listing = "\n".join(f"- {outline(root, rel)}" for rel in candidates)
    return (
        f"{format_issue(issue)}\n\n"
        f"These files might be involved, most likely first (functions and classes listed):\n"
        f"{listing}\n\n"
        f"Choose the files that must change to resolve the issue, at most {max_files}. "
        "Use the paths exactly as listed."
    )


def patch_prompt(
    issue: Issue, root: Path, files: list[str], max_chars: int, feedback: str = ""
) -> str:
    sources = "\n\n".join(f"--- {rel} ---\n{read_file(root, rel)[:max_chars]}" for rel in files)
    prompt = (
        f"Resolve this GitHub issue by editing the files below.\n\n{format_issue(issue)}\n\n"
        f"{sources}\n\n"
        "Reply with edits. Each edit replaces the text 'find' with 'replace' in 'file'. "
        "'find' must be copied exactly from the file, including indentation, and must "
        "appear in it only once; one to three whole lines is best. Change only what the "
        "fix needs, and explain the fix in one or two sentences."
    )
    if feedback:
        # Without the reminder, small models start "fixing" the error message instead.
        prompt += (
            f"\n\nYour previous reply was rejected and nothing was changed: {feedback}\n"
            "The files above are still the original. Try again to resolve the issue."
        )
    return prompt


def _normalise_path(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./")


def _choose_files(llm: LLM, prompt: str, candidates: list[str], max_files: int) -> FileChoice:
    choice = llm.complete(SYSTEM, prompt, FileChoice)
    files = [f for f in map(_normalise_path, choice.files) if f in candidates]
    # Fall back to the best search hit rather than failing on a bad choice.
    files = list(dict.fromkeys(files))[:max_files] or candidates[:1]
    return FileChoice(files=files, reason=choice.reason)


def _propose(llm: LLM, prompt: str, root: Path, files: list[str]) -> Patch:
    proposal = llm.complete(SYSTEM, prompt, PatchProposal)
    for edit in proposal.edits:
        edit.file = _normalise_path(edit.file)
    changed = apply_edits(root, proposal.edits, files)
    return Patch(
        explanation=proposal.explanation, edits=proposal.edits, diff=make_diff(root, changed)
    )


def suggest_fix(issue: Issue, root: Path, llm: LLM, settings: Settings, trace: Trace) -> Suggestion:
    prompt = classify_prompt(issue)
    classification = trace.step(
        "classify", {"prompt": prompt}, partial(llm.complete, SYSTEM, prompt, Classification)
    )
    if classification.kind not in ("bug", "feature"):
        return Suggestion("skipped", classification)

    issue_text = f"{issue.title}\n{issue.body}"
    candidates = trace.step(
        "search_code",
        {"words": sorted(issue_words(issue_text))},
        partial(rank_files, root, issue_text, settings.candidate_files),
    )
    if not candidates:
        raise AgentError("No source file mentions anything named in the issue.")

    prompt = choose_files_prompt(issue, root, candidates, settings.max_files)
    choice = trace.step(
        "choose_files",
        {"prompt": prompt, "candidates": candidates},
        partial(_choose_files, llm, prompt, candidates, settings.max_files),
    )

    feedback = ""
    for attempt in range(1, settings.max_patch_attempts + 1):
        prompt = patch_prompt(issue, root, choice.files, settings.max_file_chars, feedback)
        try:
            patch = trace.step(
                "propose_patch",
                {"attempt": attempt, "prompt": prompt},
                partial(_propose, llm, prompt, root, choice.files),
            )
        except (EditError, InvalidReplyError) as exc:
            feedback = str(exc)
            continue
        return Suggestion("suggested", classification, choice.files, patch.explanation, patch.diff)
    raise AgentError(
        f"No patch could be applied after {settings.max_patch_attempts} attempts. "
        f"Last problem: {feedback}"
    )


def execute_run(
    run_id: int, issue_number: int, target: Target, llm: LLM, store: Store, settings: Settings
) -> None:
    """Runs the agent on one issue and saves the outcome. Errors are saved on the run, not raised,
    because this runs as a background task with nobody to catch them."""
    trace = Trace(store, run_id)
    try:
        issue = trace.step(
            "fetch_issue", {"number": issue_number}, partial(target.issues.get, issue_number)
        )
        store.update_run(run_id, issue_title=issue.title)
        root = trace.step("prepare_workspace", {"repo": target.label}, target.workspace)
        suggestion = suggest_fix(issue, root, llm, settings, trace)
        store.update_run(
            run_id,
            status=suggestion.status,
            explanation=suggestion.explanation or suggestion.classification.summary,
            diff=suggestion.diff,
            finished_at=now(),
        )
    except Exception as exc:
        log.exception("Run %s failed", run_id)
        store.update_run(run_id, status="failed", error=str(exc), finished_at=now())
