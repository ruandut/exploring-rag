"""The one interface every LLM provider is used through (spec 0008).

Callers (the agent loop, retrieval, generation strategies, judges, indexing) never see a
provider SDK. They get an Adapter and speak this neutral language:

    stream_chat(model, system, history, tools) ──▶ Thinking | Text | ToolCall … then Done
    complete(model, prompt)                   ──▶ str
    embed(model, texts)                       ──▶ [[float]]
    list_models()                             ──▶ (endpoint type, [ModelInfo])

Each adapter only translates: neutral history → its provider's message format, and its
provider's stream → these events. Anything a caller would otherwise branch on per provider
belongs in the adapter instead.

History is a list of plain dicts, oldest first:
    {"role": "user", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [{"id", "name", "args"}], "raw": {...}}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str}
`raw` is the adapter's own record of the assistant turn ({"kind": ..., ...}). An adapter
resends its own raw turns unchanged — Claude's thinking blocks are signed and must come back
byte for byte between tool rounds — and rebuilds turns from other providers from the neutral
fields. History is append-only: callers never edit or drop earlier turns.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from ..catalog import ModelInfo


@dataclass
class Thinking:
    text: str


@dataclass
class Text:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict | None  # None when the model sent arguments that aren't valid JSON


@dataclass
class Done:
    # "end" | "tool_calls" | "max_tokens" | "refusal" (the model declined to answer)
    stop: str
    raw: dict = field(default_factory=dict)


Event = Thinking | Text | ToolCall | Done


@dataclass
class Tool:
    """A tool the model may call: a name, what it does, and a JSON schema for its arguments."""

    name: str
    description: str
    parameters: dict


class ProviderError(Exception):
    """A provider call failed. `permanent` errors (bad key, unknown model, bad request) won't
    get better on retry; others (timeouts, rate limits, 5xx) might."""

    def __init__(self, message: str, *, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


class ToolsUnsupported(ProviderError):
    """The model can't call tools — the agent falls back to retrieve-then-answer."""

    def __init__(self, message: str = "This model can't call tools"):
        super().__init__(message, permanent=True)


class EmbeddingsUnsupported(ProviderError):
    def __init__(self, message: str):
        super().__init__(message, permanent=True)


class Cancelled(Exception):
    """The run was cancelled (Stop pressed) while streaming."""


IsCancelled = Callable[[], bool]

# Reasoning depth, where a provider supports it. Adapters without the concept ignore it.
EFFORTS = ("low", "medium", "high", "xhigh", "max")


class Adapter(ABC):
    kind: str  # "openai" | "anthropic" | "google"

    @abstractmethod
    def stream_chat(
        self,
        model: str,
        *,
        system: str,
        history: list[dict],
        tools: list[Tool] | None = None,
        effort: str = "high",
        is_cancelled: IsCancelled = lambda: False,
    ) -> Iterator[Event]:
        """Stream one assistant turn. Ends with exactly one Done."""

    @abstractmethod
    def complete(self, model: str, prompt: str, *, max_tokens: int = 300) -> str:
        """One short, non-streaming answer to a single prompt (rewriting, reranking, judging)."""

    @abstractmethod
    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """Vectors for one batch of texts, in order. Callers do the batching."""

    @abstractmethod
    def list_models(self) -> tuple[str, list[ModelInfo]]:
        """(endpoint type, every model with its kind) for the model picker."""

    # Shared helper: the stop reason every adapter maps a refusal to.
    REFUSED = "The model declined to answer"
