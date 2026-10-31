"""A small client for the parts of the GitHub REST API the agent uses."""

import base64
import re
from urllib.parse import quote

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

    def _request(self, method: str, path: str, params=None, json=None, missing_ok=False):
        try:
            response = self._http.request(method, path, params=params, json=json)
        except httpx.HTTPError as exc:
            raise GitHubError(f"Cannot reach GitHub: {exc}") from exc
        if response.status_code == 404:
            if missing_ok:
                return None
            raise IssueNotFoundError(
                f"GitHub found nothing at {path}. Check the name, or the token's access "
                "if the repository is private."
            )
        if (
            response.status_code in (403, 429)
            and response.headers.get("x-ratelimit-remaining") == "0"
        ):
            raise GitHubError("GitHub's rate limit is used up. Set AGENT_GITHUB_TOKEN to raise it.")
        if response.status_code in (401, 403):
            raise GitHubError(
                f"GitHub refused {method} {path} ({response.status_code}). Check that "
                "AGENT_GITHUB_TOKEN is set and may write contents and pull requests."
            )
        if response.is_error:
            message = response.json().get("message", "") if response.content else ""
            raise GitHubError(f"GitHub returned {response.status_code} for {path}. {message}")
        return response.json()

    def _get(self, path: str, **params):
        return self._request("GET", path, params=params)

    def get_issue(self, repo: str, number: int) -> Issue:
        data = self._get(f"/repos/{check_repo_name(repo)}/issues/{number}")
        # GitHub's issues endpoint also returns pull requests.
        if "pull_request" in data:
            raise IssueNotFoundError(f"#{number} in {repo} is a pull request, not an issue.")
        return _to_issue(data)

    def list_open_issues(self, repo: str, limit: int = 30) -> list[Issue]:
        data = self._get(f"/repos/{check_repo_name(repo)}/issues", state="open", per_page=limit)
        return [_to_issue(item) for item in data if "pull_request" not in item]

    def open_draft_pr(
        self,
        repo: str,
        base_sha: str,
        branch: str,
        files: dict[str, str],
        title: str,
        body: str,
    ) -> str:
        """Commits files to a new branch at base_sha and opens a draft PR. Returns its URL.

        Everything goes through the REST API, so the token is never handed to git and
        nothing is pushed from the local clone.
        """
        repo = check_repo_name(repo)
        base = self._get(f"/repos/{repo}")["default_branch"]
        self._request(
            "POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": base_sha}
        )
        for path, content in sorted(files.items()):
            existing = self._request(
                "GET",
                f"/repos/{repo}/contents/{quote(path)}",
                params={"ref": branch},
                missing_ok=True,
            )
            payload = {
                "message": f"{'Update' if existing else 'Add'} {path}",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            }
            if existing:
                payload["sha"] = existing["sha"]
            self._request("PUT", f"/repos/{repo}/contents/{quote(path)}", json=payload)
        pr = self._request(
            "POST",
            f"/repos/{repo}/pulls",
            json={"title": title, "body": body, "head": branch, "base": base, "draft": True},
        )
        return pr["html_url"]


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
