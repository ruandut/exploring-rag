"""Each adapter turns its provider's own protocol into the neutral events (spec 0008).

Fake SDK clients only — no network. The agent loop's behaviour is tested once, provider-free,
in apps/agents/test_runner.py."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from anthropic.types.beta import BetaMessage

from apps.providers.llm import (
    Done,
    EmbeddingsUnsupported,
    ProviderError,
    Text,
    Thinking,
    Tool,
    ToolCall,
    ToolsUnsupported,
    make_adapter,
)

SEARCH = Tool(
    "search_documents",
    "Search the documents.",
    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
)


# --- OpenAI-compatible ---------------------------------------------------------------------


def _chunk(content=None, tool_calls=None, finish=None, **extra):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls, model_extra=extra)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


class _Stream(list):
    def close(self):
        pass


def _openai(monkeypatch, *scripts):
    adapter = make_adapter("openai", "http://fake/v1", "k", timeout=5)
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        script = scripts[len(calls) - 1]
        if isinstance(script, Exception):
            raise script
        return _Stream(script)

    adapter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    return adapter, calls


def test_openai_stream_becomes_neutral_events(monkeypatch):
    fn = SimpleNamespace(name="search_documents", arguments='{"query": ')
    fn2 = SimpleNamespace(name=None, arguments='"refunds"}')
    adapter, calls = _openai(
        monkeypatch,
        [
            _chunk(reasoning="Let me search. "),
            _chunk(tool_calls=[SimpleNamespace(index=0, id="call_1", function=fn)]),
            _chunk(
                tool_calls=[SimpleNamespace(index=0, id=None, function=fn2)], finish="tool_calls"
            ),
        ],
    )
    events = list(
        adapter.stream_chat(
            "m", system="Sys", history=[{"role": "user", "content": "Hi"}], tools=[SEARCH]
        )
    )
    assert events == [
        Thinking("Let me search. "),
        ToolCall("call_1", "search_documents", {"query": "refunds"}),
        Done("tool_calls", {"kind": "openai"}),
    ]
    assert calls[0]["messages"][0] == {"role": "system", "content": "Sys"}
    assert calls[0]["tools"][0]["function"]["name"] == "search_documents"


def test_openai_rebuilds_tool_rounds():
    adapter = make_adapter("openai", "http://fake/v1", "k", timeout=5)
    history = [
        {"role": "user", "content": "Hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "name": "search_documents", "args": {"query": "q"}}],
            "raw": {"kind": "anthropic", "content": []},
        },
        {
            "role": "tool",
            "tool_call_id": "c1",
            "name": "search_documents",
            "content": "[a.md#0]\ntext",
        },
    ]
    messages = adapter._messages("", history)
    assert messages[1]["tool_calls"][0]["function"] == {
        "name": "search_documents",
        "arguments": '{"query": "q"}',
    }
    assert messages[2] == {"role": "tool", "tool_call_id": "c1", "content": "[a.md#0]\ntext"}


def test_openai_models_without_tools_raise_tools_unsupported(monkeypatch):
    from openai import BadRequestError

    err = BadRequestError(
        "x",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body={"error": {"message": "registry.ollama.ai/library/gemma3 does not support tools"}},
    )
    adapter, _ = _openai(monkeypatch, err)
    with pytest.raises(ToolsUnsupported):
        list(
            adapter.stream_chat(
                "gemma3", system="", history=[{"role": "user", "content": "Hi"}], tools=[SEARCH]
            )
        )


# --- Anthropic ----------------------------------------------------------------------------

THINKING = {"type": "thinking", "thinking": "I should search.", "signature": "sig-abc123=="}


def _message(content, stop="end_turn"):
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )


def _delta(kind, **fields):
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type=kind, **fields))


def _anthropic(*turns):
    """turns: (stream events, final message) per call."""
    adapter = make_adapter("anthropic", "", "sk-ant", timeout=5)
    calls = []

    class _S:
        def __init__(self, events, final):
            self.events, self.final = events, final

        def __iter__(self):
            return iter(self.events)

        def get_final_message(self):
            return self.final

    @contextmanager
    def stream_cm(**params):
        calls.append(params)
        events, final = turns[len(calls) - 1]
        yield _S(events, final)

    adapter.client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(stream=stream_cm))
    )
    return adapter, calls


def test_at_0008_05_claude_thinks_then_calls_the_tool():
    tool_use = {
        "type": "tool_use",
        "id": "toolu_1",
        "name": "search_documents",
        "input": {"query": "refunds"},
    }
    adapter, calls = _anthropic(
        (
            [_delta("thinking_delta", thinking="I should search.")],
            _message([THINKING, tool_use], "tool_use"),
        )
    )
    events = list(
        adapter.stream_chat(
            "claude-opus-5-5",
            system="Sys",
            history=[{"role": "user", "content": "Hi"}],
            tools=[SEARCH],
            effort="high",
        )
    )
    assert events[0] == Thinking("I should search.")
    assert events[1] == ToolCall("toolu_1", "search_documents", {"query": "refunds"})
    assert events[2].stop == "tool_calls" and events[2].raw["content"][0] == THINKING

    params = calls[0]
    assert params["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert params["output_config"] == {"effort": "high"}
    assert not {"temperature", "top_p", "top_k", "tool_choice"} & set(params)
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert params["tools"][0]["eager_input_streaming"] is True
    assert params["fallbacks"] == "default" and params["betas"] == [
        "server-side-fallback-2026-07-01"
    ]


def test_at_0008_05_thinking_blocks_go_back_unchanged():
    tool_use = {
        "type": "tool_use",
        "id": "toolu_1",
        "name": "search_documents",
        "input": {"query": "refunds"},
    }
    adapter, calls = _anthropic(
        ([], _message([THINKING, tool_use], "tool_use")),
        ([_delta("text_delta", text="30 days")], _message([{"type": "text", "text": "30 days"}])),
    )
    first = list(
        adapter.stream_chat(
            "claude-opus-5-5",
            system="",
            history=[{"role": "user", "content": "Hi"}],
            tools=[SEARCH],
        )
    )
    done = first[-1]
    history = [
        {"role": "user", "content": "Hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "toolu_1", "name": "search_documents", "args": {"query": "refunds"}}
            ],
            "raw": done.raw,
        },
        {
            "role": "tool",
            "tool_call_id": "toolu_1",
            "name": "search_documents",
            "content": "[a.md#0]\nThe window is 30 days.",
        },
    ]
    list(adapter.stream_chat("claude-opus-5-5", system="", history=history, tools=[SEARCH]))
    sent = calls[1]["messages"]
    assert sent[1] == {"role": "assistant", "content": [THINKING, tool_use]}  # signature intact
    assert sent[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "[a.md#0]\nThe window is 30 days.",
    }


def test_at_0008_07_a_refusal_is_reported():
    adapter, _ = _anthropic(
        (
            [_delta("text_delta", text="Partial answer")],
            _message([{"type": "text", "text": "Partial answer"}], "refusal"),
        )
    )
    events = list(
        adapter.stream_chat(
            "claude-haiku-5-5", system="", history=[{"role": "user", "content": "Hi"}]
        )
    )
    assert events[-1].stop == "refusal"


def test_haiku_gets_no_fallbacks():
    adapter, calls = _anthropic(([], _message([{"type": "text", "text": "Hi"}])))
    list(
        adapter.stream_chat(
            "claude-haiku-5-5", system="", history=[{"role": "user", "content": "Hi"}]
        )
    )
    assert "fallbacks" not in calls[0] and "betas" not in calls[0]


def test_anthropic_has_no_embeddings():
    with pytest.raises(EmbeddingsUnsupported, match="Anthropic has no embeddings API"):
        make_adapter("anthropic", "", "k", timeout=5).embed("m", ["x"])


def test_anthropic_errors_keep_the_providers_message():
    import anthropic

    from apps.providers.llm.anthropic_adapter import _wrap

    response = SimpleNamespace(status_code=401, headers={}, request=None)
    err = anthropic.AuthenticationError(
        "401",
        response=response,
        body={
            "type": "error",
            "error": {"type": "authentication_error", "message": "invalid x-api-key"},
        },
    )
    wrapped = _wrap(err)
    assert (str(wrapped), wrapped.permanent) == ("invalid x-api-key", True)


# --- Google -------------------------------------------------------------------------------


def _google(*chunks_per_call):
    from google.genai import types

    adapter = make_adapter("google", "", "k", timeout=5)
    calls = []

    def generate_content_stream(model, contents, config):
        calls.append({"model": model, "contents": contents, "config": config})
        return [
            types.GenerateContentResponse.model_validate(c) for c in chunks_per_call[len(calls) - 1]
        ]

    adapter.client = SimpleNamespace(
        models=SimpleNamespace(generate_content_stream=generate_content_stream)
    )
    return adapter, calls


def test_at_0008_06_gemini_calls_the_tool_and_keeps_its_signature():
    call = {
        "function_call": {"id": "fc1", "name": "search_documents", "args": {"query": "refunds"}},
        "thought_signature": "c2ln",
    }
    adapter, calls = _google(
        [
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Thinking…", "thought": True}, call],
                        },
                        "finish_reason": "STOP",
                    }
                ]
            }
        ],
        [
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "30 days"}]},
                        "finish_reason": "STOP",
                    }
                ]
            }
        ],
    )
    events = list(
        adapter.stream_chat(
            "gemini-fake", system="Sys", history=[{"role": "user", "content": "Hi"}], tools=[SEARCH]
        )
    )
    assert events[0] == Thinking("Thinking…")
    assert events[1] == ToolCall("fc1", "search_documents", {"query": "refunds"})
    done = events[2]
    assert done.stop == "tool_calls"
    history = [
        {"role": "user", "content": "Hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "fc1", "name": "search_documents", "args": {"query": "refunds"}}],
            "raw": done.raw,
        },
        {
            "role": "tool",
            "tool_call_id": "fc1",
            "name": "search_documents",
            "content": "[a.md#0]\ntext",
        },
    ]
    assert [
        e for e in adapter.stream_chat("gemini-fake", system="", history=history, tools=[SEARCH])
    ] == [
        Text("30 days"),
        Done(
            "end", events[-1].raw | {"content": {"role": "model", "parts": [{"text": "30 days"}]}}
        ),
    ]
    model_turn = calls[1]["contents"][1]
    assert model_turn.parts[1].thought_signature == b"sig"  # resent unchanged
    assert calls[1]["contents"][2].parts[0].function_response.name == "search_documents"


def test_gemini_safety_stop_is_a_refusal():
    adapter, _ = _google(
        [
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "Part"}]},
                        "finish_reason": "SAFETY",
                    }
                ]
            }
        ]
    )
    assert (
        list(
            adapter.stream_chat(
                "gemini-fake", system="", history=[{"role": "user", "content": "Hi"}]
            )
        )[-1].stop
        == "refusal"
    )


def test_provider_errors_are_neutral():
    assert issubclass(ToolsUnsupported, ProviderError) and issubclass(
        EmbeddingsUnsupported, ProviderError
    )
