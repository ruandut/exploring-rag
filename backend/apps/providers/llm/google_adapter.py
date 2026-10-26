"""Gemini through the Gemini API (the official `google-genai` SDK).

Gemini-specific details stay here: thought summaries (include_thoughts), function calling
with automatic calling disabled (the agent loop runs tools itself), safety stops mapped to a
refusal, and the model turn's parts — with their thought signatures — kept as `raw` and sent
back unchanged on the next round.
"""

from collections.abc import Iterator

from google import genai
from google.genai import errors, types

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
)

_REFUSALS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"}


def _wrap(exc: errors.APIError) -> ProviderError:
    return ProviderError(exc.message or str(exc), permanent=isinstance(exc, errors.ClientError))


class GoogleAdapter(Adapter):
    kind = "google"

    def __init__(self, base_url: str, api_key: str, *, timeout: float):
        # base_url is only set for tests and proxies; blank means the SDK's default endpoint.
        options = types.HttpOptions(timeout=int(timeout * 1000), base_url=base_url or None)
        self.client = genai.Client(api_key=api_key or "not-set", http_options=options)

    @staticmethod
    def _contents(history: list[dict]) -> list[types.Content]:
        out: list[types.Content] = []
        for turn in history:
            role = turn["role"]
            if role == "assistant":
                raw = turn.get("raw") or {}
                if raw.get("kind") == "google":
                    out.append(types.Content.model_validate(raw["content"]))
                    continue
                parts = [types.Part(text=turn["content"])] if turn.get("content") else []
                parts += [
                    types.Part(
                        function_call=types.FunctionCall(
                            id=c["id"], name=c["name"], args=c["args"] or {}
                        )
                    )
                    for c in turn.get("tool_calls") or []
                ]
                out.append(types.Content(role="model", parts=parts or [types.Part(text="")]))
            elif role == "tool":
                part = types.Part(
                    function_response=types.FunctionResponse(
                        id=turn["tool_call_id"],
                        name=turn["name"],
                        response={"result": turn["content"]},
                    )
                )
                # Every result of one round goes back in a single user turn.
                if (
                    out
                    and out[-1].role == "user"
                    and out[-1].parts
                    and out[-1].parts[0].function_response
                ):
                    out[-1].parts.append(part)
                else:
                    out.append(types.Content(role="user", parts=[part]))
            else:
                out.append(types.Content(role="user", parts=[types.Part(text=turn["content"])]))
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
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.parameters,
                        )
                        for t in tools
                    ]
                )
            ]
            if tools
            else None,
        )
        parts: list[types.Part] = []
        finish = None
        try:
            for chunk in self.client.models.generate_content_stream(
                model=model, contents=self._contents(history), config=config
            ):
                if is_cancelled():
                    raise Cancelled
                candidate = (chunk.candidates or [None])[0]
                if candidate is None:
                    continue
                finish = candidate.finish_reason or finish
                for part in (candidate.content.parts if candidate.content else None) or []:
                    parts.append(part)
                    if part.thought and part.text:
                        yield Thinking(part.text)
                    elif part.text:
                        yield Text(part.text)
        except errors.APIError as exc:
            raise _wrap(exc) from exc

        raw = {
            "kind": self.kind,
            "content": types.Content(role="model", parts=parts).model_dump(
                mode="json", exclude_none=True
            ),
        }
        reason = getattr(finish, "name", str(finish or ""))
        if reason in _REFUSALS:
            yield Done("refusal", raw)
            return
        calls = [p.function_call for p in parts if p.function_call]
        for i, fc in enumerate(calls):
            yield ToolCall(
                fc.id or f"call_{i}", fc.name or "", dict(fc.args) if fc.args is not None else None
            )
        stop = "tool_calls" if calls else "max_tokens" if reason == "MAX_TOKENS" else "end"
        yield Done(stop, raw)

    def complete(self, model, prompt, *, max_tokens=300) -> str:
        # No max_output_tokens: Gemini's thinking counts against it, and a small cap would
        # leave nothing for the answer. Prompts here ask for short replies instead.
        try:
            res = self.client.models.generate_content(model=model, contents=prompt)
        except errors.APIError as exc:
            raise _wrap(exc) from exc
        candidate = (res.candidates or [None])[0]
        if candidate is not None and getattr(candidate.finish_reason, "name", "") in _REFUSALS:
            raise ProviderError(self.REFUSED, permanent=True)
        return (res.text or "").strip()

    def embed(self, model, texts):
        try:
            res = self.client.models.embed_content(model=model, contents=texts)
        except errors.APIError as exc:
            raise _wrap(exc) from exc
        return [list(e.values or []) for e in res.embeddings or []]

    def list_models(self):
        try:
            listed = list(self.client.models.list())
        except errors.APIError as exc:
            raise _wrap(exc) from exc
        out = []
        for m in sorted(listed, key=lambda m: m.name or ""):
            model_id = (m.name or "").removeprefix("models/")
            actions = set(m.supported_actions or [])
            if "embedContent" in actions:
                known = catalog.classify(model_id)
                out.append(catalog.ModelInfo(model_id, "embedding", "endpoint", known.dimensions))
            elif "generateContent" in actions:
                out.append(catalog.ModelInfo(model_id, "chat", "endpoint", None, True))
            else:
                out.append(catalog.classify(model_id))
        return "google", out
