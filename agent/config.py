from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Agent settings. Override any of them with AGENT_* environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="AGENT_", extra="ignore"
    )

    ollama_host: str = "http://localhost:11434"
    # 3B fits in 8 GB of RAM; 7B writes better patches if the machine has the memory.
    llm_model: str = "qwen2.5-coder:3b"
    # Keep the model in memory between steps (Ollama's default is 5m) to skip reloads.
    llm_keep_alive: str = "30m"
    # A fix is a few edits; the cap stops a runaway reply taking minutes on a CPU.
    max_output_tokens: int = 1024
    # Longer files are cut so the prompt fits the model's context window.
    max_file_chars: int = 12_000

    # Optional. Public repos work without it, but GitHub then allows 60 requests an hour.
    github_token: str = ""
    github_api: str = "https://api.github.com"

    database_path: Path = PROJECT_ROOT / "data" / "agent.db"
    workspaces_dir: Path = PROJECT_ROOT / "data" / "workspaces"
    # The bundled demo repo with planted bugs, and the issues that describe them.
    demo_repo: Path = PROJECT_ROOT / "demo_repo"
    demo_issues: Path = PROJECT_ROOT / "benchmark" / "issues.jsonl"

    # How many candidate files the model chooses from, and how many it may change.
    candidate_files: int = 8
    max_files: int = 2
    # Attempts at a patch that applies and passes the tests; each retry shows the model
    # what went wrong.
    max_patch_attempts: int = 3
    # Attempts at a regression test that fails on the current code, i.e. shows the bug.
    max_test_attempts: int = 2

    # The Docker image tests run in (built from sandbox/Dockerfile) and its limits.
    sandbox_image: str = "issue-agent-sandbox"
    sandbox_timeout_s: int = 120
    sandbox_memory: str = "512m"
    sandbox_cpus: str = "1"

    # LangGraph saves each run's state here, so a run waiting for approval survives restarts.
    checkpoint_path: Path = PROJECT_ROOT / "data" / "checkpoints.db"
    # Approved patches for the demo repo, which has no GitHub repository to open a PR on.
    patches_dir: Path = PROJECT_ROOT / "data" / "patches"


@lru_cache
def get_settings() -> Settings:
    return Settings()
