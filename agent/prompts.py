"""Every prompt the agent sends to the model."""

from pathlib import Path

from agent.issues import Issue
from agent.workspace import outline, read_file

SYSTEM = (
    "You are a careful software engineer who fixes GitHub issues with the smallest correct "
    "change. Reply only with JSON in the requested shape."
)
# Issue text is written by anyone; the cap keeps a huge issue from filling the prompt.
MAX_ISSUE_CHARS = 4000
MAX_EXAMPLE_TEST_CHARS = 1500


def format_issue(issue: Issue) -> str:
    return f"Issue #{issue.number}: {issue.title}\n\n{issue.body[:MAX_ISSUE_CHARS]}"


def _sources(root: Path, files: list[str], max_chars: int) -> str:
    return "\n\n".join(f"--- {rel} ---\n{read_file(root, rel)[:max_chars]}" for rel in files)


def _rejected(feedback: str) -> str:
    # Without the reminder, small models start "fixing" the error message instead.
    return (
        f"\n\nYour previous reply was rejected and nothing was changed: {feedback}\n"
        "The files above are still the original. Try again to resolve the issue."
    )


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


def test_prompt(
    issue: Issue,
    root: Path,
    files: list[str],
    test_path: str,
    example_test: str,
    max_chars: int,
    feedback: str = "",
) -> str:
    example = (
        f"An existing test in the repository, to show how tests import the code:\n"
        f"{example_test[:MAX_EXAMPLE_TEST_CHARS]}\n\n"
        if example_test
        else ""
    )
    prompt = (
        f"Write a pytest test that reproduces this GitHub issue.\n\n{format_issue(issue)}\n\n"
        f"{_sources(root, files, max_chars)}\n\n{example}"
        "Use the examples and expected values given in the issue. The test must FAIL on "
        "the code above, because that shows the bug, and pass once the bug is fixed. "
        "Write one short test function with a few asserts, and the imports it needs. "
        f"It will be saved as {test_path} and run with pytest from the repository root.\n\n"
        "Reply with the complete Python source of the test file in 'code', starting with "
        "its imports. Do not reply with the file name."
    )
    if feedback:
        prompt += f"\n\nYour previous test was rejected: {feedback}\nWrite a new test."
    return prompt


def patch_prompt(
    issue: Issue,
    root: Path,
    files: list[str],
    max_chars: int,
    regression_test: str = "",
    feedback: str = "",
) -> str:
    target = (
        f"This test reproduces the issue. It fails now and must pass after your change:\n"
        f"{regression_test}\n\n"
        if regression_test
        else ""
    )
    prompt = (
        f"Resolve this GitHub issue by editing the files below.\n\n{format_issue(issue)}\n\n"
        f"{_sources(root, files, max_chars)}\n\n{target}"
        "Reply with edits. Each edit replaces the text 'find' with 'replace' in 'file'. "
        "'find' must be copied exactly from the file, including indentation, and must "
        "appear in it only once; one to three whole lines is best. Change only what the "
        "fix needs, and explain the fix in one or two sentences."
    )
    if feedback:
        prompt += _rejected(feedback)
    return prompt
