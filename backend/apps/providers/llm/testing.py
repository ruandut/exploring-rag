"""A scripted Adapter for tests: no network, no SDK. Every app's tests use this one fake
instead of faking a particular provider's client."""

from .base import Adapter, Cancelled, Done, ProviderError, Text, Thinking, ToolCall


class FakeAdapter(Adapter):
    kind = "fake"

    def __init__(self, *turns, replies=None, embed_dims: int = 8, models=None, error=None):
        # turns: one list of events (or an exception) per stream_chat call.
        self.turns = list(turns)
        self.replies = list(replies or [])  # complete() answers, in order ("OK" when empty)
        self.embed_dims = embed_dims
        self.models = models or []
        self.error = error  # raised by embed() / complete() when set
        self.calls: list[dict] = []  # what each stream_chat call received
        self.prompts: list[str] = []
        self.embedded: list[int] = []  # batch sizes

    def stream_chat(
        self, model, *, system, history, tools=None, effort="high", is_cancelled=lambda: False
    ):
        self.calls.append(
            {
                "model": model,
                "system": system,
                "history": [dict(t) for t in history],
                "tools": tools,
                "effort": effort,
            }
        )
        script = self.turns.pop(0) if self.turns else [Text("OK"), Done("end")]
        if isinstance(script, Exception):
            raise script
        for event in script:
            if is_cancelled():
                raise Cancelled
            yield event

    def complete(self, model, prompt, *, max_tokens=300):
        if self.error:
            raise self.error
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else "OK"

    def embed(self, model, texts):
        if self.error:
            raise self.error
        self.embedded.append(len(texts))
        return [[0.1] * self.embed_dims for _ in texts]

    def list_models(self):
        return "fake", self.models


__all__ = ["Done", "FakeAdapter", "ProviderError", "Text", "Thinking", "ToolCall"]
