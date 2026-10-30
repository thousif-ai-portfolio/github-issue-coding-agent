"""Shared fixtures. Tests never call a real model or GitHub, so they run offline in seconds."""

import pytest

from agent.config import Settings
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


def median_replies(*patches: dict) -> list:
    """Model replies for demo issue #8: classify, choose a file, then each patch attempt."""
    return [
        {"kind": "bug", "summary": "median must average the two middle values."},
        {"files": ["shopkit/stats.py"], "reason": "median is defined there."},
        *patches,
    ]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(database_path=tmp_path / "agent.db", workspaces_dir=tmp_path / "workspaces")


@pytest.fixture
def store(settings) -> Store:
    return Store(settings.database_path)
