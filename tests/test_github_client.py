import httpx
import pytest

from agent.github_client import GitHubClient, GitHubError, check_repo_name
from agent.issues import IssueNotFoundError

ISSUE = {
    "number": 7,
    "title": "Bug",
    "body": "Broken",
    "html_url": "https://github.com/o/r/issues/7",
}


def client_for(handler, token: str = "") -> GitHubClient:
    return GitHubClient(token=token, transport=httpx.MockTransport(handler))


def test_get_issue_sends_the_token():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=ISSUE)

    issue = client_for(handler, token="secret").get_issue("o/r", 7)
    assert (issue.number, issue.title, issue.body) == (7, "Bug", "Broken")
    assert seen == {"path": "/repos/o/r/issues/7", "auth": "Bearer secret"}


def test_pull_requests_are_not_issues():
    pr = {**ISSUE, "pull_request": {"url": "..."}}
    with pytest.raises(IssueNotFoundError, match="pull request"):
        client_for(lambda r: httpx.Response(200, json=pr)).get_issue("o/r", 7)
    issues = client_for(lambda r: httpx.Response(200, json=[ISSUE, pr])).list_open_issues("o/r")
    assert [i.number for i in issues] == [7]


def test_missing_issue():
    with pytest.raises(IssueNotFoundError):
        client_for(lambda r: httpx.Response(404, json={})).get_issue("o/r", 99)


def test_rate_limit_gives_a_helpful_message():
    def handler(request):
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={})

    with pytest.raises(GitHubError, match="AGENT_GITHUB_TOKEN"):
        client_for(handler).get_issue("o/r", 1)


def test_null_body_becomes_empty_text():
    issue = client_for(lambda r: httpx.Response(200, json={**ISSUE, "body": None})).get_issue(
        "o/r", 7
    )
    assert issue.body == ""


@pytest.mark.parametrize("name", ["owner", "o/r/x", "../etc", "o/r?x=1", "o/.."])
def test_rejects_bad_repo_names(name):
    with pytest.raises(ValueError):
        check_repo_name(name)
