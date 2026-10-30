"""A small client for the parts of the GitHub REST API the agent uses."""

import re

import httpx

from agent.issues import Issue, IssueNotFoundError

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubError(RuntimeError):
    """GitHub could not be reached or refused the request."""


def check_repo_name(repo: str) -> str:
    # The name goes into URL paths, so anything but "owner/name" is rejected.
    if not REPO_PATTERN.match(repo) or ".." in repo:
        raise ValueError(f"Expected a repository as owner/name, got {repo!r}.")
    return repo


class GitHubClient:
    def __init__(
        self, token: str = "", base_url: str = "https://api.github.com", transport=None
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(
            base_url=base_url, headers=headers, timeout=30, transport=transport
        )

    def _get(self, path: str, **params):
        try:
            response = self._http.get(path, params=params)
        except httpx.HTTPError as exc:
            raise GitHubError(f"Cannot reach GitHub: {exc}") from exc
        if response.status_code == 404:
            raise IssueNotFoundError(
                f"GitHub found nothing at {path}. Check the name, or the token's access "
                "if the repository is private."
            )
        if (
            response.status_code in (403, 429)
            and response.headers.get("x-ratelimit-remaining") == "0"
        ):
            raise GitHubError("GitHub's rate limit is used up. Set AGENT_GITHUB_TOKEN to raise it.")
        if response.is_error:
            raise GitHubError(f"GitHub returned {response.status_code} for {path}.")
        return response.json()

    def get_issue(self, repo: str, number: int) -> Issue:
        data = self._get(f"/repos/{check_repo_name(repo)}/issues/{number}")
        # GitHub's issues endpoint also returns pull requests.
        if "pull_request" in data:
            raise IssueNotFoundError(f"#{number} in {repo} is a pull request, not an issue.")
        return _to_issue(data)

    def list_open_issues(self, repo: str, limit: int = 30) -> list[Issue]:
        data = self._get(f"/repos/{check_repo_name(repo)}/issues", state="open", per_page=limit)
        return [_to_issue(item) for item in data if "pull_request" not in item]


def _to_issue(data: dict) -> Issue:
    return Issue(
        number=data["number"],
        title=data["title"],
        body=data.get("body") or "",
        url=data.get("html_url", ""),
    )


class GitHubIssues:
    """The open issues of one repository, as an issue source."""

    def __init__(self, client: GitHubClient, repo: str) -> None:
        self._client = client
        self._repo = check_repo_name(repo)

    def get(self, number: int) -> Issue:
        return self._client.get_issue(self._repo, number)

    def list_open(self) -> list[Issue]:
        return self._client.list_open_issues(self._repo)
