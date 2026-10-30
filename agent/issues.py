"""Where issues come from: a GitHub repository or the bundled demo issues."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class IssueNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    url: str = ""


class IssueSource(Protocol):
    def get(self, number: int) -> Issue: ...

    def list_open(self) -> list[Issue]: ...


class DemoIssues:
    """The planted-bug issues in benchmark/issues.jsonl, so the agent runs without GitHub."""

    def __init__(self, path: Path) -> None:
        self._issues = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                self._issues[row["number"]] = Issue(row["number"], row["title"], row["body"])

    def get(self, number: int) -> Issue:
        try:
            return self._issues[number]
        except KeyError:
            raise IssueNotFoundError(f"There is no demo issue #{number}.") from None

    def list_open(self) -> list[Issue]:
        return list(self._issues.values())
