"""The agent loop with a scripted fake adapter (no network, no Hatchet, no provider SDK).

The loop is provider-agnostic: these tests feed it neutral events. How each provider's stream
becomes those events is tested next to the adapters (apps/providers/llm/test_adapters.py)."""

import pytest

from apps.agents import runner
from apps.agents.models import Agent
from apps.providers.llm import ProviderError, ToolsUnsupported
from apps.providers.llm.testing import Done, FakeAdapter, Text, Thinking, ToolCall
from apps.providers.models import Connection, ProviderConfig
from apps.rag.models import EmbeddingIndex
from apps.rag.retrieval import Retrieved


@pytest.fixture
def agent(user):
    ProviderConfig.objects.create(owner=user, base_url="http://fake/v1", chat_model="fake-chat")
    return Agent.objects.create(owner=user, name="Helper", system_message="Be brief.")


@pytest.fixture
def emb(user):
    return EmbeddingIndex.objects.create(owner=user, name="All", model="e", all_documents=True)


@pytest.fixture
def chunks(monkeypatch):
    found = [
        Retrieved(1, 1, "handbook.md", 0, "", "The refund window is 30 days.", "", 0.9),
    ]
    monkeypatch.setattr(runner.retrieval, "search", lambda *a, **k: found)
    monkeypatch.setattr(runner, "make_embedder", lambda adapter, model: lambda t: [[0.0]])
    return found


def use(monkeypatch, adapter):
    monkeypatch.setattr("apps.providers.services.build_adapter", lambda *a, **k: adapter)
    return adapter


def search(query, id="call_1"):
    return [
        ToolCall(id, "search_documents", {"query": query}),
        Done("tool_calls", {"kind": "fake", "n": 1}),
    ]


def test_agent_searches_then_answers_with_citations(db, user, agent, emb, chunks, monkeypatch):
    model = use(
        monkeypatch,
        FakeAdapter(
            [Thinking("Let me search. "), *search("refund window")],
            [Text("The window is 30 days "), Text("[handbook.md#0]."), Done("end")],
        ),
    )
    events = []
    result = runner.run(
        user=user,
        agent=agent,
        messages=[{"role": "user", "content": "Refunds?"}],
        emit=events.append,
        embedding=emb,
    )
    assert [e["type"] for e in events] == [
        "agent.thinking",
        "agent.tool_call",
        "agent.retrieval",
        "agent.token",
        "agent.token",
    ]
    assert result.answer == "The window is 30 days [handbook.md#0]."
    assert result.retrieved[0]["document"] == "handbook.md"
    assert result.mode == "agentic"
    # Round two carries round one unchanged — including the adapter's raw turn — then the
    # tool result, tagged so the model can cite it.
    second = model.calls[1]["history"]
    assert second[1] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "call_1", "name": "search_documents", "args": {"query": "refund window"}}
        ],
        "raw": {"kind": "fake", "n": 1},
    }
    assert second[2]["role"] == "tool" and "[handbook.md#0]" in second[2]["content"]
    assert "Be brief." in model.calls[0]["system"]
    assert model.calls[0]["effort"] == "high"


def test_models_without_tools_fall_back_to_retrieve_then_answer(
    db, user, agent, emb, chunks, monkeypatch
):
    model = use(
        monkeypatch, FakeAdapter(ToolsUnsupported(), [Text("30 days [handbook.md#0]"), Done("end")])
    )
    result = runner.run(
        user=user,
        agent=agent,
        messages=[{"role": "user", "content": "Refunds?"}],
        emit=lambda e: None,
        embedding=emb,
    )
    assert result.mode == "pipeline"
    assert result.answer == "30 days [handbook.md#0]"
    assert model.calls[1]["tools"] is None
    assert "Passages from my documents" in model.calls[1]["history"][-1]["content"]


def test_invalid_tool_arguments_go_back_as_an_error(db, user, agent, emb, chunks, monkeypatch):
    model = use(
        monkeypatch,
        FakeAdapter(
            [ToolCall("call_1", "search_documents", None), Done("tool_calls")],
            [Text("Sorry"), Done("end")],
        ),
    )
    result = runner.run(
        user=user,
        agent=agent,
        messages=[{"role": "user", "content": "Hi"}],
        emit=lambda e: None,
        embedding=emb,
    )
    assert result.tool_calls == []  # nothing was searched with a guessed query
    assert "Invalid arguments" in model.calls[1]["history"][-1]["content"]


def test_a_refusal_is_an_error_even_after_text_streamed(db, user, agent, monkeypatch):
    use(monkeypatch, FakeAdapter([Text("Partial answer"), Done("refusal")]))
    with pytest.raises(ProviderError, match="The model declined to answer"):
        runner.run(
            user=user,
            agent=agent,
            messages=[{"role": "user", "content": "Hi"}],
            emit=lambda e: None,
        )


def test_the_chat_picks_the_connection_and_model(db, user, agent, emb, chunks, monkeypatch):
    connection = Connection.objects.create(
        owner=user, name="Ollama", base_url="http://localhost:11434/v1"
    )
    model = use(monkeypatch, FakeAdapter([Text("Hi"), Done("end")]))
    result = runner.run(
        user=user,
        agent=agent,
        messages=[{"role": "user", "content": "Hi"}],
        emit=lambda e: None,
        embedding=emb,
        connection=connection,
        model="gemma4:e4b",
    )
    assert model.calls[0]["model"] == "gemma4:e4b"
    assert result.model == "Ollama · gemma4:e4b"


def test_with_no_embedding_the_model_answers_alone(db, user, agent, monkeypatch):
    model = use(monkeypatch, FakeAdapter([Text("Hello from the model"), Done("end")]))
    result = runner.run(
        user=user, agent=agent, messages=[{"role": "user", "content": "Hi"}], emit=lambda e: None
    )
    assert result.mode == "model" and result.answer == "Hello from the model"
    assert model.calls[0]["tools"] is None  # nothing to search, so no search tool
    assert model.calls[0]["system"] == "Be brief."


def test_the_agents_effort_reaches_the_adapter(db, user, agent, monkeypatch):
    agent.effort = "max"
    model = use(monkeypatch, FakeAdapter())
    runner.run(
        user=user, agent=agent, messages=[{"role": "user", "content": "Hi"}], emit=lambda e: None
    )
    assert model.calls[0]["effort"] == "max"


def test_cancellation_stops_streaming(db, user, agent, emb, chunks, monkeypatch):
    use(monkeypatch, FakeAdapter([Text("a"), Text("b"), Text("c"), Done("end")]))
    tokens = []
    with pytest.raises(runner.Cancelled):
        runner.run(
            user=user,
            agent=agent,
            messages=[{"role": "user", "content": "Hi"}],
            emit=tokens.append,
            is_cancelled=lambda: len(tokens) >= 1,
            embedding=emb,
        )
    assert [t["text"] for t in tokens] == ["a"]
