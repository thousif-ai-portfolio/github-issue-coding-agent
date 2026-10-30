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
    # Called when the run starts, because cloning can take a while.
    workspace: Callable[[], Path]


def resolve_target(
    source: str, repo: str | None, settings: Settings, github: GitHubClient | None = None
) -> Target:
    if source == "demo":
        return Target("demo", DemoIssues(settings.demo_issues), lambda: settings.demo_repo)
    if not repo:
        raise ValueError("A GitHub repository (owner/name) is required.")
    github = github or GitHubClient(settings.github_token, settings.github_api)
    return Target(
        repo, GitHubIssues(github, repo), lambda: sync_repo(repo, settings.workspaces_dir)
    )
