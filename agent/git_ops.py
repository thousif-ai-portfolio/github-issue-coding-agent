"""Git commands, run as subprocesses. Week 1 only needs a fresh copy of the repository."""

import subprocess
from pathlib import Path

from agent.github_client import check_repo_name


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f"git {args[0]} could not run: {exc}") from exc
    if result.returncode != 0:
        raise GitError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def sync_repo(repo: str, workspaces: Path) -> Path:
    """Shallow-clones a public GitHub repository, or resets an earlier clone to its latest commit.

    The token is never put in the clone URL, where git would save it in .git/config.
    """
    target = workspaces / check_repo_name(repo).replace("/", "__")
    if (target / ".git").exists():
        git("fetch", "--depth", "1", "origin", "HEAD", cwd=target)
        git("reset", "--hard", "FETCH_HEAD", cwd=target)
        git("clean", "-fdx", cwd=target)
    else:
        workspaces.mkdir(parents=True, exist_ok=True)
        git("clone", "--depth", "1", f"https://github.com/{repo}.git", str(target))
    return target


def head_commit(repo_dir: Path) -> str:
    return git("rev-parse", "HEAD", cwd=repo_dir)
