"""The REST API. Runs take minutes on a CPU, so starting one returns at once and the
client polls GET /api/runs/{id} for the result."""

from dataclasses import asdict
from functools import lru_cache
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException

from agent.config import Settings, get_settings
from agent.github_client import GitHubError
from agent.issues import IssueNotFoundError
from agent.llm import LLM, OllamaLLM
from agent.pipeline import execute_run
from agent.schemas import IssueOut, RunDetail, RunRequest, RunSummary
from agent.store import Store
from agent.targets import resolve_target

app = FastAPI(title="GitHub Issue Coding Agent", version="0.1.0")


@lru_cache
def get_store() -> Store:
    return Store(get_settings().database_path)


@lru_cache
def get_llm() -> LLM:
    settings = get_settings()
    return OllamaLLM(
        settings.ollama_host,
        settings.llm_model,
        settings.llm_keep_alive,
        settings.max_output_tokens,
    )


@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "model": settings.llm_model}


@app.get("/api/issues", response_model=list[IssueOut])
def list_issues(
    source: Literal["github", "demo"] = "github",
    repo: str | None = None,
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    try:
        target = resolve_target(source, repo, settings)
        return [asdict(issue) for issue in target.issues.list_open()]
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IssueNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/runs", status_code=202, response_model=RunSummary)
def start_run(
    request: RunRequest,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    store: Store = Depends(get_store),
    llm: LLM = Depends(get_llm),
) -> dict:
    target = resolve_target(request.source, request.repo, settings)
    run_id = store.create_run(target.label, request.issue_number, llm.model)
    background.add_task(execute_run, run_id, request.issue_number, target, llm, store, settings)
    return store.get_run(run_id)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(store: Store = Depends(get_store)) -> list[dict]:
    return store.list_runs()


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int, store: Store = Depends(get_store)) -> dict:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"There is no run {run_id}.")
    return run
