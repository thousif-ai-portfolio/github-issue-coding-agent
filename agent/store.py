"""SQLite storage for runs and the trace of every step the agent took."""

import json
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    explanation TEXT NOT NULL DEFAULT '',
    diff TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""

RUN_FIELDS = {"issue_title", "status", "explanation", "diff", "error", "finished_at"}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # A connection per call: runs execute in background threads.
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _write(self, sql: str, params: tuple) -> int:
        with closing(self._connect()) as conn, conn:
            return conn.execute(sql, params).lastrowid

    def create_run(self, repo: str, issue_number: int, model: str) -> int:
        return self._write(
            "INSERT INTO runs (repo, issue_number, status, model, created_at) "
            "VALUES (?, ?, 'running', ?, ?)",
            (repo, issue_number, model, now()),
        )

    def update_run(self, run_id: int, **fields: str) -> None:
        unknown = set(fields) - RUN_FIELDS
        if unknown:
            raise ValueError(f"Unknown run fields: {unknown}")
        columns = ", ".join(f"{name} = ?" for name in fields)
        self._write(f"UPDATE runs SET {columns} WHERE id = ?", (*fields.values(), run_id))

    def add_step(
        self, run_id: int, name: str, status: str, input: dict, output: dict, duration_ms: int
    ) -> None:
        self._write(
            "INSERT INTO steps (run_id, name, status, input, output, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, name, status, json.dumps(input), json.dumps(output), duration_ms, now()),
        )

    def list_runs(self, limit: int = 50) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in rows]

    def get_run(self, run_id: int) -> dict | None:
        with closing(self._connect()) as conn:
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                return None
            steps = conn.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY id", (run_id,))
            return {
                **dict(run),
                "steps": [
                    {**dict(s), "input": json.loads(s["input"]), "output": json.loads(s["output"])}
                    for s in steps
                ],
            }


def to_jsonable(value):
    if isinstance(value, BaseModel):
        return value.model_dump()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


class Trace:
    """Records each step of one run: its input, its output or error, and how long it took."""

    def __init__(self, store: Store, run_id: int) -> None:
        self._store = store
        self.run_id = run_id

    def step(self, name: str, input: dict, action: Callable[[], T]) -> T:
        start = time.perf_counter()
        try:
            result = action()
        except Exception as exc:
            self._record(name, "error", input, {"error": str(exc)}, start)
            raise
        output = to_jsonable(result)
        self._record(
            name, "ok", input, output if isinstance(output, dict) else {"result": output}, start
        )
        return result

    def _record(self, name: str, status: str, input: dict, output: dict, start: float) -> None:
        ms = round((time.perf_counter() - start) * 1000)
        self._store.add_step(self.run_id, name, status, input, output, ms)
