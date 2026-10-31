"""The REST API. Runs take minutes on a CPU, so starting one returns at once and the
client polls GET /api/runs/{id}. A run that passes its tests waits for a person to
approve or reject it before anything is sent to GitHub."""

from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from agent.config import Settings, get_settings
from agent.github_client import GitHubClient, GitHubError
from agent.graph import Deps, resume_run, start_run
from agent.issues import IssueNotFoundError
from agent.llm import OllamaLLM
from agent.sandbox import DockerSandbox
from agent.schemas import IssueOut, ReviewRequest, RunDetail, RunRequest, RunSummary
from agent.store import Store
from agent.targets import resolve_target

app = FastAPI(title="GitHub Issue Coding Agent", version="0.2.0")


@lru_cache
def get_deps() -> Deps:
    settings = get_settings()
    deps = Deps(
        llm=OllamaLLM(
            settings.ollama_host,
            settings.llm_model,
            settings.llm_keep_alive,
            settings.max_output_tokens,
        ),
        sandbox=DockerSandbox(
            settings.sandbox_image,
            settings.sandbox_timeout_s,
            settings.sandbox_memory,
            settings.sandbox_cpus,
        ),
        store=Store(settings.database_path),
        settings=settings,
        github=GitHubClient(settings.github_token, settings.github_api),
    )
    # Runs execute inside this process, so any still "running" were cut off by a restart.
    deps.store.fail_interrupted()
    return deps


@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "model": settings.llm_model}


@app.get("/api/issues", response_model=list[IssueOut])
def list_issues(
    source: Literal["github", "demo"] = "github",
    repo: str | None = None,
    deps: Deps = Depends(get_deps),
) -> list[dict]:
    try:
        target = resolve_target(source, repo, deps.settings, deps.github)
        return [asdict(issue) for issue in target.issues.list_open()]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IssueNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/runs", status_code=202, response_model=RunSummary)
def create_run(
    request: RunRequest, background: BackgroundTasks, deps: Deps = Depends(get_deps)
) -> dict:
    label = request.repo if request.source == "github" else "demo"
    run_id = deps.store.create_run(label, request.issue_number, deps.llm.model)
    background.add_task(start_run, run_id, request.source, request.repo, request.issue_number, deps)
    return deps.store.get_run(run_id)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(deps: Deps = Depends(get_deps)) -> list[dict]:
    return deps.store.list_runs()


def _get_run(run_id: int, deps: Deps) -> dict:
    run = deps.store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"There is no run {run_id}.")
    return run


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int, deps: Deps = Depends(get_deps)) -> dict:
    return _get_run(run_id, deps)


def _review(run_id: int, approved: bool, comment: str, background, deps: Deps) -> dict:
    run = _get_run(run_id, deps)
    # One atomic update, so two clicks at the same moment cannot both resume the run.
    if not deps.store.claim_for_review(run_id):
        raise HTTPException(409, f"Run {run_id} is {run['status']}, not awaiting approval.")
    background.add_task(resume_run, run_id, approved, comment, deps)
    return deps.store.get_run(run_id)


@app.post("/api/runs/{run_id}/approve", status_code=202, response_model=RunSummary)
def approve_run(
    run_id: int,
    background: BackgroundTasks,
    review: ReviewRequest,
    deps: Deps = Depends(get_deps),
) -> dict:
    """Needs a JSON body ({} is fine): a browser only sends one cross-site after a CORS
    check this API never passes, so another web page cannot approve a run."""
    return _review(run_id, True, review.comment, background, deps)


@app.post("/api/runs/{run_id}/reject", status_code=202, response_model=RunSummary)
def reject_run(
    run_id: int,
    background: BackgroundTasks,
    review: ReviewRequest,
    deps: Deps = Depends(get_deps),
) -> dict:
    return _review(run_id, False, review.comment, background, deps)


DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


def mount_dashboard(app: FastAPI, directory: Path) -> bool:
    """Serves the built React dashboard at /, after the API routes so they win.
    It is only there once built (cd dashboard && npm run build); in development
    `npm run dev` serves it instead."""
    if not (directory / "index.html").is_file():
        return False
    app.mount("/", StaticFiles(directory=directory, html=True), name="dashboard")
    return True


mount_dashboard(app, DASHBOARD_DIR)
