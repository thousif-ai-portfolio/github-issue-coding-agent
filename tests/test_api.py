import pytest
from fastapi.testclient import TestClient

from agent.config import get_settings
from agent.main import app, get_llm, get_store
from tests.conftest import MEDIAN_FIX, FakeLLM, median_replies


@pytest.fixture
def client(settings, store):
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: FakeLLM(median_replies(MEDIAN_FIX))
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lists_demo_issues(client):
    response = client.get("/api/issues", params={"source": "demo"})
    assert response.status_code == 200
    assert len(response.json()) == 8


def test_run_starts_at_once_and_finishes_in_the_background(client):
    response = client.post("/api/runs", json={"source": "demo", "issue_number": 8})
    assert response.status_code == 202
    assert response.json()["status"] == "running"

    # TestClient runs background tasks before returning, so the run is already done.
    run = client.get(f"/api/runs/{response.json()['id']}").json()
    assert run["status"] == "suggested"
    assert run["model"] == "fake-model"
    assert "+        return (ordered[middle - 1] + ordered[middle]) / 2" in run["diff"]
    assert len(run["steps"]) == 6
    assert [r["id"] for r in client.get("/api/runs").json()] == [run["id"]]


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
