"""Reading a checked-out repository: listing, searching and outlining its source files."""

import ast
import re
from pathlib import Path

# Week 1 handles Python repositories only.
SOURCE_SUFFIXES = {".py"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "build"}
# Common words that would make every file look relevant.
STOPWORDS = {
    "the", "and", "for", "but", "not", "with", "should", "returns", "return", "gives",
    "instead", "this", "that", "are", "was", "when", "from", "into", "its", "any", "even",
    "expected", "result", "true", "false", "none", "def", "self",
}  # fmt: skip


class WorkspaceError(ValueError):
    pass


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_")


def list_source_files(root: Path) -> list[str]:
    """Source files as paths relative to the root, with forward slashes."""
    files = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.suffix in SOURCE_SUFFIXES and not SKIP_DIRS.intersection(rel.parts):
            files.append(rel.as_posix())
    return sorted(files)


def read_file(root: Path, rel: str) -> str:
    path = (root / rel).resolve()
    # A model-chosen path must not escape the repository, e.g. "../../.env".
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise WorkspaceError(f"{rel} is not a file in the repository.")
    # Line endings are normalised so the model's copied text matches on Windows too.
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def issue_words(text: str) -> set[str]:
    words = {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)}
    return words - STOPWORDS


def rank_files(root: Path, text: str, limit: int) -> list[str]:
    """Source files (tests excluded) ordered by how many words of the issue they contain.

    A cheap, predictable first filter: the model then picks from a short list instead of
    guessing among every file in the repository.
    """
    words = issue_words(text)
    scored = []
    for rel in list_source_files(root):
        if is_test_file(rel):
            continue
        content = read_file(root, rel).lower()
        names = {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", content)}
        score = len(words & names)
        # A function or module named in the issue is the strongest hint.
        score += 3 * len(words & set(defined_names(root, rel)))
        score += 3 * (Path(rel).stem.lower() in words)
        if score:
            scored.append((score, rel))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [rel for _, rel in scored[:limit]]


def defined_names(root: Path, rel: str) -> list[str]:
    """Top-level functions and classes, lowercased; empty if the file does not parse."""
    try:
        tree = ast.parse(read_file(root, rel))
    except SyntaxError:
        return []
    return [
        node.name.lower()
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]


def outline(root: Path, rel: str) -> str:
    """One line describing a file, e.g. "shopkit/text.py: slugify, truncate"."""
    names = defined_names(root, rel)
    return f"{rel}: {', '.join(names)}" if names else rel
