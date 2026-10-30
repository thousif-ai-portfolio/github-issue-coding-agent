"""Checks the benchmark itself: the demo repo's own tests pass, and every planted bug is real."""

import json
import subprocess
import sys

from agent.config import Settings

settings = Settings()
HIDDEN = settings.demo_issues.parent / "hidden_tests"


def pytest_in_demo_repo(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=settings.demo_repo,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_demo_repo_tests_pass():
    result = pytest_in_demo_repo()
    assert result.returncode == 0, result.stdout


def test_every_issue_has_a_hidden_test_that_fails_today():
    issues = [json.loads(line) for line in settings.demo_issues.read_text().splitlines()]
    tests = [HIDDEN / issue["hidden_test"] for issue in issues]
    assert all(test.is_file() for test in tests)

    result = pytest_in_demo_repo(*map(str, tests))
    assert f"{len(issues)} failed" in result.stdout, result.stdout
