"""Any OpenAI-compatible endpoint: OpenAI, OpenRouter, Ollama, vLLM, Groq… (the `openai` SDK)."""

import json
from collections.abc import Iterator

from openai import (
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    UnprocessableEntityError,
)

from .. import catalog
from .base import (
    Adapter,
    Cancelled,
    Done,
    Event,
    IsCancelled,
    ProviderError,
    Text,
    Thinking,
    ToolCall,
    ToolsUnsupported,
)

_PERMANENT = (
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)


def _message(exc: Exception) -> str:
    # Surface the provider's own message (e.g. "Incorrect API key provided") when there is one.
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return str(exc) or exc.__class__.__name__


def _wrap(exc: OpenAIError) -> ProviderError:
    return ProviderError(_message(exc), permanent=isinstance(exc, _PERMANENT))


class OpenAICompatible(Adapter):
    kind = "openai"

    def __init__(self, base_url: str, api_key: str, *, timeout: float):
        self.base_url = base_url
        self.api_key = api_key
        # Local servers like Ollama ignore the key, but the SDK requires a non-empty one.
        self.client = OpenAI(
            base_url=base_url, api_key=api_key or "not-needed", timeout=timeout, max_retries=0
        )

    # --- chat -----------------------------------------------------------------------------

    def _messages(self, system: str, history: list[dict]) -> list[dict]:
        out = [{"role": "system", "content": system}] if system else []
        for turn in history:
            if turn["role"] == "assistant":
                msg = {"role": "assistant", "content": turn.get("content") or None}
                if turn.get("tool_calls"):
                    msg["tool_calls"] = [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c["args"] or {}),
                            },
                        }
                        for c in turn["tool_calls"]
                    ]
                out.append(msg)
            elif turn["role"] == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": turn["tool_call_id"],
                        "content": turn["content"],
                    }
                )
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
        kwargs = {"model": model, "messages": self._messages(system, history), "stream": True}
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        try:
            stream = self.client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            # Ollama and others reject `tools` for models that can't call them (400 "… does
            # not support tools"): the agent switches to retrieve-then-answer.
            if tools and "tool" in _message(exc).lower():
                raise ToolsUnsupported(_message(exc)) from exc
            raise _wrap(exc) from exc
        except OpenAIError as exc:
            raise _wrap(exc) from exc

        calls: dict[int, dict] = {}
        finish = None
        try:
            for chunk in stream:
                if is_cancelled():
                    raise Cancelled
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish = choice.finish_reason or finish
                delta = choice.delta
                # Reasoning isn't in the OpenAI schema; DeepSeek / OpenRouter / Ollama add it as
                # an extra field (reasoning_content or reasoning).
                extra = delta.model_extra or {}
                reasoning = extra.get("reasoning_content") or extra.get("reasoning")
                if reasoning:
                    yield Thinking(reasoning)
                if delta.content:
                    yield Text(delta.content)
                for tc in delta.tool_calls or []:
                    slot = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    slot["id"] = tc.id or slot["id"] or f"call_{tc.index}"
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments
        except OpenAIError as exc:
            raise _wrap(exc) from exc
        finally:
            stream.close()

        for i in sorted(calls):
            c = calls[i]
            try:
                args = json.loads(c["arguments"] or "{}")
            except json.JSONDecodeError:
                args = None
            yield ToolCall(c["id"], c["name"], args if isinstance(args, dict) else None)
        stop = "tool_calls" if calls else "max_tokens" if finish == "length" else "end"
        if finish == "content_filter":
            stop = "refusal"
        yield Done(stop, {"kind": self.kind})

    def complete(self, model, prompt, *, max_tokens=300) -> str:
        try:
            res = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0,
            )
        except OpenAIError as exc:
            raise _wrap(exc) from exc
        return (res.choices[0].message.content or "").strip()

    # --- embeddings & models ----------------------------------------------------------------

    def embed(self, model, texts) -> list[list[float]]:
        try:
            res = self.client.embeddings.create(model=model, input=texts)
        except OpenAIError as exc:
            raise _wrap(exc) from exc
        # Providers may return items out of order; `index` is authoritative.
        return [item.embedding for item in sorted(res.data, key=lambda d: d.index)]

    def list_models(self):
        endpoint = catalog.endpoint_type(self.base_url, self.api_key)
        try:
            listed = sorted(self.client.models.list(), key=lambda m: m.id)
        except (OpenAIError, APIStatusError) as exc:
            raise _wrap(exc) from exc
        ids = [m.id for m in listed]
        if endpoint == "ollama":
            return endpoint, catalog.ollama_models(catalog.ollama_root(self.base_url), ids)
        if endpoint == "openrouter":
            out = []
            for m in listed:
                arch = (m.model_extra or {}).get("architecture") or {}
                outputs = set(arch.get("output_modalities") or [])
                if "embeddings" in outputs:
                    out.append(catalog.ModelInfo(m.id, "embedding", "endpoint"))
                elif outputs:
                    out.append(catalog.ModelInfo(m.id, "chat", "endpoint"))
                else:
                    out.append(catalog.classify(m.id))
            return endpoint, out
        return endpoint, [catalog.classify(m) for m in ids]
