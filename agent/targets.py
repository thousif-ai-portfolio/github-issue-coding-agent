"""What a run works on: where its issue comes from and where the code is checked out."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent.config import Settings
from agent.git_ops import sync_repo
from agent.github_client import GitHubClient, GitHubIssues
from agent.issues import DemoIssues, IssueSource


@dataclass(frozen=True)
class Target:
    label: str
    issues: IssueSource
    # Called with the run id when the run starts, because cloning can take a while.
    workspace: Callable[[int], Path]


def resolve_target(
    source: str, repo: str | None, settings: Settings, github: GitHubClient | None = None
) -> Target:
    if source == "demo":
        return Target("demo", DemoIssues(settings.demo_issues), lambda _: settings.demo_repo)
    if not repo:
        raise ValueError("A GitHub repository (owner/name) is required.")
    github = github or GitHubClient(settings.github_token, settings.github_api)

    # One clone per run: a second run on the same repository cannot change the commit
    # this run tested, which is the commit its draft PR starts from.
    def workspace(run_id: int) -> Path:
        return sync_repo(repo, settings.workspaces_dir / f"run-{run_id}")

    return Target(repo, GitHubIssues(github, repo), workspace)
