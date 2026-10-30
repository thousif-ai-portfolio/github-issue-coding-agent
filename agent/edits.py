"""Applying the model's edits and turning them into a reviewable diff.

The model returns find-and-replace edits instead of a unified diff: small models rarely
get diff line numbers right, but can copy a few lines of code exactly. The diff is then
produced here, so it is always well formed.
"""

import difflib
from pathlib import Path

from agent.schemas import Edit
from agent.workspace import read_file


class EditError(ValueError):
    """The edits cannot be applied. The message is shown to the model on retry."""


def apply_edits(root: Path, edits: list[Edit], allowed_files: list[str]) -> dict[str, str]:
    """Returns the new content of each changed file. Nothing is written to disk."""
    changed: dict[str, str] = {}
    for edit in edits:
        if edit.file not in allowed_files:
            raise EditError(
                f"{edit.file} is not one of the files you may change: {', '.join(allowed_files)}."
            )
        if not edit.find:
            raise EditError(f"An edit to {edit.file} has an empty 'find'.")
        content = changed.get(edit.file, read_file(root, edit.file))
        count = content.count(edit.find)
        if count == 0:
            raise EditError(
                f"The 'find' text was not found in {edit.file}. Copy it exactly from the "
                "file, including indentation."
            )
        if count > 1:
            raise EditError(
                f"The 'find' text appears {count} times in {edit.file}. Include more "
                "surrounding lines so it matches only once."
            )
        changed[edit.file] = content.replace(edit.find, edit.replace, 1)
    changed = {f: c for f, c in changed.items() if c != read_file(root, f)}
    if not changed:
        raise EditError("The edits do not change anything.")
    for rel, content in changed.items():
        check_syntax(rel, content)
    return changed


def check_syntax(rel: str, content: str) -> None:
    # Small models often lose indentation in 'replace'; catching it here costs nothing.
    if not rel.endswith(".py"):
        return
    try:
        # compile, not ast.parse: only the compiler rejects e.g. 'return' outside a function.
        # The code is compiled, never run.
        compile(content, rel, "exec", dont_inherit=True)
    except SyntaxError as exc:
        raise EditError(
            f"After your edits {rel} is not valid Python ({exc.msg}, line {exc.lineno}). "
            "Keep the file's indentation in 'replace'."
        ) from None


def make_diff(root: Path, changed: dict[str, str]) -> str:
    """A unified diff of the changes; files that do not exist yet show as added."""
    parts = []
    for rel, new in sorted(changed.items()):
        exists = (root / rel).is_file()
        old = read_file(root, rel) if exists else ""
        parts.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{rel}" if exists else "/dev/null",
                tofile=f"b/{rel}",
            )
        )
    return "".join(parts)
