"""Shared fixtures. Tests never call a real model or GitHub, so they run offline in seconds."""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from agent.config import Settings
from agent.github_client import GitHubClient
from agent.graph import Deps
from agent.sandbox import TestResult, copy_repo, tail
from agent.store import Store


class FakeLLM:
    """Replays prepared replies in order and remembers every prompt it was sent."""

    model = "fake-model"

    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, system, prompt, schema):
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return schema.model_validate(reply)


class LocalSandbox:
    """Runs pytest on a temporary copy without Docker. Only for tests, which run the
    demo repo's own code; the agent itself always uses DockerSandbox."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_tests(self, root, changes, tests=None):
        self.calls.append({"changes": dict(changes), "tests": tests})
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            copy_repo(root, repo, changes)
            start = time.perf_counter()
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *(tests or [])],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=120,
            )
        ms = round((time.perf_counter() - start) * 1000)
        return TestResult(result.returncode == 0, result.returncode, tail(result.stdout), ms)


MEDIAN_TEST = (
    "from shopkit.stats import median\n\n\n"
    "def test_median_of_even_count():\n"
    "    assert median([1, 2, 3, 4]) == 2.5\n"
)
# Passes on the buggy code, so it does not show the bug.
WEAK_TEST = (
    "from shopkit.stats import median\n\n\ndef test_median():\n    assert median([3, 1, 2]) == 2\n"
)
MEDIAN_FIX = {
    "explanation": "For an even count, return the mean of the two middle values.",
    "edits": [
        {
            "file": "shopkit/stats.py",
            "find": "    return ordered[middle]\n",
            "replace": (
                "    if len(ordered) % 2 == 0:\n"
                "        return (ordered[middle - 1] + ordered[middle]) / 2\n"
                "    return ordered[middle]\n"
            ),
        }
    ],
}
# What qwen2.5-coder:3b actually proposed: applies cleanly, but is wrong.
WRONG_FIX = {
    "explanation": "Use the lower middle value.",
    "edits": [
        {
            "file": "shopkit/stats.py",
            "find": "    middle = len(ordered) // 2\n",
            "replace": "    middle = len(ordered) // 2 - 1\n",
        }
    ],
}


def median_replies(*rest) -> list:
    """Model replies for demo issue #8: classify and choose a file, then whatever follows."""
    return [
        {"kind": "bug", "summary": "median must average the two middle values."},
        {"files": ["shopkit/stats.py"], "reason": "median is defined there."},
        *rest,
    ]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "agent.db",
        checkpoint_path=tmp_path / "checkpoints.db",
        workspaces_dir=tmp_path / "workspaces",
        patches_dir=tmp_path / "patches",
    )


@pytest.fixture
def store(settings) -> Store:
    return Store(settings.database_path)


@pytest.fixture
def make_deps(settings, store):
    def make(replies: list, github: GitHubClient | None = None) -> Deps:
        return Deps(
            llm=FakeLLM(replies),
            sandbox=LocalSandbox(),
            store=store,
            settings=settings,
            github=github or GitHubClient(),
        )

    return make
