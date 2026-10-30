"""Runs a repository's tests, with the agent's changes applied, inside a locked-down container.

Generated code is untrusted: it could delete files, read secrets or call out to the
internet. So it never runs on the host. Each test run gets a fresh copy of the repository
in a container with no network, a read-only filesystem, no Linux capabilities, an
unprivileged user and limits on memory, CPU, processes and time.
"""

import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent.workspace import SKIP_DIRS

# Enough of pytest's report to see what failed, without filling the model's prompt.
MAX_OUTPUT_CHARS = 4000


class SandboxError(RuntimeError):
    """The sandbox itself failed (e.g. Docker is not running), as opposed to failing tests."""


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class, despite the name

    passed: bool
    exit_code: int
    output: str
    duration_ms: int
    timed_out: bool = False

    @property
    def collection_error(self) -> bool:
        # pytest exit codes: 1 tests failed, 2 interrupted or import error, 4 usage, 5 none ran.
        return self.exit_code in (2, 3, 4, 5)


class Sandbox(Protocol):
    def run_tests(
        self, root: Path, changes: dict[str, str], tests: list[str] | None = None
    ) -> TestResult: ...


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def copy_repo(root: Path, target: Path, changes: dict[str, str]) -> None:
    shutil.copytree(root, target, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    for rel, content in changes.items():
        path = (target / rel).resolve()
        if not path.is_relative_to(target.resolve()):
            raise SandboxError(f"Refusing to write outside the repository: {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def tail(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT_CHARS else "...\n" + text[-MAX_OUTPUT_CHARS:]


class DockerSandbox:
    def __init__(
        self, image: str, timeout_s: int = 120, memory: str = "512m", cpus: str = "1"
    ) -> None:
        self._image = image
        self._timeout_s = timeout_s
        self._memory = memory
        self._cpus = cpus

    def command(self, repo_dir: Path, name: str, tests: list[str]) -> list[str]:
        return [
            "docker", "run", "--rm", "--name", name,
            "--network", "none",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "1000:1000",
            "--memory", self._memory, "--cpus", self._cpus, "--pids-limit", "128",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--volume", f"{repo_dir}:/work:ro",
            self._image,
            "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--color=no", *tests,
        ]  # fmt: skip

    def run_tests(
        self, root: Path, changes: dict[str, str], tests: list[str] | None = None
    ) -> TestResult:
        with tempfile.TemporaryDirectory(prefix="agent-sandbox-") as tmp:
            repo_dir = Path(tmp) / "repo"
            copy_repo(root, repo_dir, changes)
            name = f"agent-sandbox-{uuid.uuid4().hex[:12]}"
            start = time.perf_counter()
            try:
                result = subprocess.run(
                    self.command(repo_dir, name, tests or []),
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                )
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "kill", name], capture_output=True)
                return TestResult(
                    False, -1, f"Tests did not finish within {self._timeout_s}s.",
                    round((time.perf_counter() - start) * 1000), timed_out=True,
                )  # fmt: skip
            except OSError as exc:
                raise SandboxError(f"Cannot start Docker: {exc}") from exc
            ms = round((time.perf_counter() - start) * 1000)
            # Docker's own failures (daemon down, image missing) use exit codes 125-127.
            if result.returncode in (125, 126, 127):
                raise SandboxError(
                    f"Docker could not run the sandbox: {result.stderr.strip()[:300]} "
                    f"Is Docker running, and was the image built (docker build -t "
                    f"{self._image} sandbox)?"
                )
            output = tail((result.stdout + result.stderr).strip())
            return TestResult(result.returncode == 0, result.returncode, output, ms)
