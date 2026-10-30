import pytest
from fastapi.testclient import TestClient

from agent.main import app, get_deps
from tests.conftest import MEDIAN_FIX, MEDIAN_TEST, median_replies


@pytest.fixture
def client(make_deps):
    app.dependency_overrides[get_deps] = lambda: make_deps(
        median_replies({"code": MEDIAN_TEST}, MEDIAN_FIX)
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lists_demo_issues(client):
    response = client.get("/api/issues", params={"source": "demo"})
    assert response.status_code == 200
    assert len(response.json()) == 18


def test_run_waits_for_approval_then_finishes(client):
    response = client.post("/api/runs", json={"source": "demo", "issue_number": 8})
    assert response.status_code == 202
    assert response.json()["status"] == "running"
    run_id = response.json()["id"]

    # TestClient runs background tasks before returning, so the run has reached the review.
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "awaiting_approval"
    assert run["model"] == "fake-model"
    assert "+        return (ordered[middle - 1] + ordered[middle]) / 2" in run["diff"]
    assert run["regression_test"] == MEDIAN_TEST

    assert client.post(f"/api/runs/{run_id}/approve").status_code == 202
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "approved"
    # A finished run cannot be reviewed again.
    assert client.post(f"/api/runs/{run_id}/reject").status_code == 409
    assert [r["id"] for r in client.get("/api/runs").json()] == [run_id]


def test_reject_with_a_comment(client):
    run_id = client.post("/api/runs", json={"source": "demo", "issue_number": 8}).json()["id"]
    response = client.post(f"/api/runs/{run_id}/reject", json={"comment": "Too risky"})
    assert response.status_code == 202
    run = client.get(f"/api/runs/{run_id}").json()
    assert (run["status"], run["error"]) == ("rejected", "Too risky")


@pytest.mark.parametrize(
    "body",
    [
        {"source": "github", "issue_number": 1},
        {"source": "github", "repo": "../secrets", "issue_number": 1},
        {"source": "demo", "issue_number": 0},
    ],
)
def test_rejects_bad_run_requests(client, body):
    assert client.post("/api/runs", json=body).status_code == 422


def test_unknown_run(client):
    assert client.get("/api/runs/999").status_code == 404
    assert client.post("/api/runs/999/approve").status_code == 404


def test_serves_built_dashboard_without_hiding_the_api(tmp_path):
    from fastapi import FastAPI

    from agent.main import mount_dashboard

    site = FastAPI()

    @site.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    assert not mount_dashboard(site, tmp_path)  # not built yet: nothing mounted
    (tmp_path / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    assert mount_dashboard(site, tmp_path)

    browser = TestClient(site)
    assert "<div id=root>" in browser.get("/").text
    assert browser.get("/api/health").json() == {"status": "ok"}
