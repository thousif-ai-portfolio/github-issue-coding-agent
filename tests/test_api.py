import pytest
from fastapi.testclient import TestClient

from agent import cli
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

    assert client.post(f"/api/runs/{run_id}/approve", json={}).status_code == 202
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "approved"
    # A finished run cannot be reviewed again.
    assert client.post(f"/api/runs/{run_id}/reject", json={}).status_code == 409
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
    assert client.post("/api/runs/999/approve", json={}).status_code == 404


def test_approval_needs_a_json_body_so_other_websites_cannot_send_it(client):
    run_id = client.post("/api/runs", json={"source": "demo", "issue_number": 1}).json()["id"]
    # What a cross-site form or no-cors fetch can send: no JSON body.
    assert client.post(f"/api/runs/{run_id}/approve").status_code == 422
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    assert (
        client.post(f"/api/runs/{run_id}/approve", content="x=1", headers=form).status_code == 422
    )


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


def test_numbers_beyond_the_database_range_are_rejected(client):
    too_big = 2**63
    assert (
        client.post("/api/runs", json={"source": "demo", "issue_number": too_big}).status_code
        == 422
    )
    assert client.get(f"/api/runs/{too_big}").status_code == 422


def test_server_start_marks_runs_cut_off_by_a_restart_as_failed(client, store):
    run_id = store.create_run("demo", 1, "m")
    with TestClient(app):  # starting the app runs its lifespan
        pass
    assert store.get_run(run_id)["status"] == "failed"


def test_cli_does_not_fail_runs_the_server_is_working_on(store, make_deps, monkeypatch, capsys):
    run_id = store.create_run("demo", 1, "m")
    monkeypatch.setattr(cli, "get_deps", lambda: make_deps([]))
    assert cli.main(["issues", "not a repo"]) == 1
    assert "Cannot list issues" in capsys.readouterr().out
    assert store.get_run(run_id)["status"] == "running"
