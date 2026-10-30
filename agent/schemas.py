"""The shapes of the model's replies and of the API's requests and responses."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from agent.github_client import check_repo_name

# --- What the model must reply with (Ollama enforces these JSON schemas) ---


class Classification(BaseModel):
    kind: Literal["bug", "feature", "question", "other"]
    summary: str = Field(description="One sentence saying what must change.")


class FileChoice(BaseModel):
    files: list[str]
    reason: str


class Edit(BaseModel):
    file: str
    find: str = Field(description="Lines copied exactly from the file.")
    replace: str = Field(description="The lines that take their place.")


class PatchProposal(BaseModel):
    explanation: str = Field(description="What was wrong and how the edits fix it.")
    edits: list[Edit] = Field(min_length=1)


# --- API ---


class RunRequest(BaseModel):
    source: Literal["github", "demo"] = "github"
    repo: str | None = Field(default=None, examples=["owner/name"])
    issue_number: int = Field(ge=1)

    @model_validator(mode="after")
    def _repo_for_github(self):
        if self.source == "github":
            if not self.repo:
                raise ValueError("repo is required when source is github")
            check_repo_name(self.repo)
        return self


class IssueOut(BaseModel):
    number: int
    title: str
    body: str
    url: str


class StepOut(BaseModel):
    name: str
    status: str
    input: dict
    output: dict
    duration_ms: int
    created_at: str


class RunSummary(BaseModel):
    id: int
    repo: str
    issue_number: int
    issue_title: str
    status: str
    created_at: str
    finished_at: str | None


class RunDetail(RunSummary):
    model: str
    explanation: str
    diff: str
    error: str
    steps: list[StepOut]
