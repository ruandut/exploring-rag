"""Claude through Anthropic's Messages API (the official `anthropic` SDK).

What's specific to Claude stays in this file:
- adaptive thinking with display "summarized", so reasoning streams as readable text (the
  default, "omitted", streams empty thinking blocks);
- effort set explicitly (Claude Opus 5.5 defaults to "medium");
- no temperature / top_p / top_k (rejected by current models);
- tools with eager_input_streaming; tool_choice left at auto (forced tool use returns 400);
- the system prompt is cached (tools + system are identical on every round);
- server-side refusal fallbacks on the models that support them;
- the assistant turn's content blocks — thinking blocks with their signatures — are returned
  as `raw` and resent unchanged on the next round, as current models require.
"""

from collections.abc import Iterator

import anthropic

from .. import catalog
from .base import (
    Adapter,
    Cancelled,
    Done,
    EmbeddingsUnsupported,
    Event,
    IsCancelled,
    ProviderError,
    Text,
    Thinking,
    ToolCall,
)

DEFAULT_BASE_URL = "https://api.anthropic.com"
MAX_TOKENS = 16_000
# Thinking counts against max_tokens, so short completions (relevance checks, Test connection)
# still need room to think before they answer.
MIN_COMPLETE_TOKENS = 2_048
# Models that accept fallbacks: "default" (a declined request is retried on a suitable model).
FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_PERMANENT_STATUS = {400, 401, 403, 404, 413, 422}


def _wrap(exc: anthropic.AnthropicError) -> ProviderError:
    if isinstance(exc, anthropic.APIStatusError):
        body = exc.body if isinstance(exc.body, dict) else {}
        err = body.get("error") if isinstance(body.get("error"), dict) else {}
        message = err.get("message") or exc.message
        return ProviderError(str(message), permanent=exc.status_code in _PERMANENT_STATUS)
    return ProviderError(str(exc) or exc.__class__.__name__)


class AnthropicAdapter(Adapter):
    kind = "anthropic"

    def __init__(self, base_url: str, api_key: str, *, timeout: float):
        # base_url is only set for tests and proxies. Blank means Anthropic's own API — passed
        # explicitly, so an ANTHROPIC_BASE_URL in the server's environment can't silently
        # redirect a user's requests somewhere else.
        self.client = anthropic.Anthropic(
            api_key=api_key or "not-set",
            base_url=base_url or DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=0,
        )

    def _request(self, model: str, effort: str) -> dict:
        params = {
            "model": model,
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": effort},
        }
        if model in FALLBACK_MODELS:
            params |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        return params

    @staticmethod
    def _messages(history: list[dict]) -> list[dict]:
        out: list[dict] = []
        for turn in history:
            role = turn["role"]
            if role == "assistant":
                raw = turn.get("raw") or {}
                if raw.get("kind") == "anthropic":
                    content = raw["content"]  # byte for byte: signed thinking blocks included
                else:
                    content = (
                        [{"type": "text", "text": turn["content"]}] if turn.get("content") else []
                    ) + [
                        {
                            "type": "tool_use",
                            "id": c["id"],
                            "name": c["name"],
                            "input": c["args"] or {},
                        }
                        for c in turn.get("tool_calls") or []
                    ]
                out.append(
                    {"role": "assistant", "content": content or [{"type": "text", "text": ""}]}
                )
            elif role == "tool":
                block = {
                    "type": "tool_result",
                    "tool_use_id": turn["tool_call_id"],
                    "content": turn["content"],
                }
                # Every result of one round goes back in a single user message.
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            else:
                out.append({"role": "user", "content": turn["content"]})
        return out

    def stream_chat(
        self,
        model,
        *,
        system,
        history,
        tools=None,
        effort="high",
        is_cancelled: IsCancelled = lambda: False,
    ) -> Iterator[Event]:
        params = self._request(model, effort) | {
            "max_tokens": MAX_TOKENS,
            "messages": self._messages(history),
        }
        if system:
            params["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        if tools:
            params["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                    "eager_input_streaming": True,
                }
                for t in tools
            ]
        try:
            with self.client.beta.messages.stream(**params) as stream:
                for event in stream:
                    if is_cancelled():
                        raise Cancelled
                    if event.type == "content_block_delta":
                        if event.delta.type == "thinking_delta" and event.delta.thinking:
                            yield Thinking(event.delta.thinking)
                        elif event.delta.type == "text_delta" and event.delta.text:
                            yield Text(event.delta.text)
                final = stream.get_final_message()
        except ValueError as exc:
            # With eager input streaming the SDK raises ValueError for tool input it can't
            # parse at all. There's no tool_use id to answer, so the round is retried.
            raise ProviderError(f"The model sent a malformed tool call: {exc}") from exc
        except anthropic.AnthropicError as exc:
            raise _wrap(exc) from exc

        raw = {
            "kind": self.kind,
            "content": [b.model_dump(exclude_none=True) for b in final.content],
        }
        if final.stop_reason == "refusal":
            yield Done("refusal", raw)
            return
        calls = [b for b in final.content if b.type == "tool_use"]
        for b in calls:
            yield ToolCall(b.id, b.name, b.input if isinstance(b.input, dict) else None)
        if final.stop_reason == "max_tokens":
            stop = "max_tokens"  # a truncated tool input parses as a partial object: don't run it
        else:
            stop = "tool_calls" if calls else "end"
        yield Done(stop, raw)

    def complete(self, model, prompt, *, max_tokens=300) -> str:
        try:
            res = self.client.beta.messages.create(
                **self._request(model, "low"),
                max_tokens=max(max_tokens, MIN_COMPLETE_TOKENS),
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.AnthropicError as exc:
            raise _wrap(exc) from exc
        if res.stop_reason == "refusal":
            raise ProviderError(self.REFUSED, permanent=True)
        return "".join(b.text for b in res.content if b.type == "text").strip()

    def embed(self, model, texts):
        raise EmbeddingsUnsupported("Anthropic has no embeddings API — use another connection.")

    def list_models(self):
        try:
            ids = sorted(m.id for m in self.client.models.list())
        except anthropic.AnthropicError as exc:
            raise _wrap(exc) from exc
        return "anthropic", [catalog.ModelInfo(m, "chat", "endpoint", None, True) for m in ids]
