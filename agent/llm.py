"""The language model, served locally by Ollama. Every reply is JSON checked against a schema."""

from typing import Protocol, TypeVar

import httpx
import ollama
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model could not be reached or returned an error."""


class InvalidReplyError(LLMError):
    """The model answered, but not in the requested shape. Worth retrying."""


class LLM(Protocol):
    model: str

    def complete(self, system: str, prompt: str, schema: type[T]) -> T: ...


class OllamaLLM:
    def __init__(self, host: str, model: str, keep_alive: str, max_tokens: int) -> None:
        self.model = model
        self._host = host
        self._keep_alive = keep_alive
        self._max_tokens = max_tokens
        self._client = ollama.Client(host=host)

    def complete(self, system: str, prompt: str, schema: type[T]) -> T:
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                # Constrains the reply to valid JSON of this shape.
                format=schema.model_json_schema(),
                # Same issue, same patch: makes benchmark results repeatable.
                options={"temperature": 0, "num_predict": self._max_tokens},
                keep_alive=self._keep_alive,
            )
        except ollama.ResponseError as exc:
            raise LLMError(
                f"Ollama error: {exc.error}. Did you run 'ollama pull {self.model}'?"
            ) from exc
        except (ConnectionError, httpx.HTTPError) as exc:
            raise LLMError(f"Cannot reach Ollama at {self._host}. Is Ollama running?") from exc
        try:
            return schema.model_validate_json(response.message.content or "")
        except ValidationError as exc:
            # A reply cut off by the token limit is the usual cause.
            raise InvalidReplyError(
                f"The reply did not match {schema.__name__}: {exc.errors()[0]['msg']}"
            ) from exc
