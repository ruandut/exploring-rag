"""The agent loop with a scripted fake model (no network, no Hatchet)."""

from types import SimpleNamespace

import pytest
from openai import BadRequestError

from apps.agents import runner
from apps.agents.models import Agent
from apps.providers.models import Connection, ProviderConfig
from apps.rag.models import EmbeddingIndex
from apps.rag.retrieval import Retrieved


def delta(content=None, tool_calls=None, **extra):
    d = SimpleNamespace(content=content, tool_calls=tool_calls, model_extra=extra)
    return SimpleNamespace(choices=[SimpleNamespace(delta=d)])


def tool_call(query):
    fn = SimpleNamespace(name="search_documents", arguments=f'{{"query": "{query}"}}')
    return [SimpleNamespace(index=0, id="call_1", function=fn)]


class Stream(list):
    def close(self):
        pass


class ScriptedModel:
    """Returns one scripted stream per chat.completions.create call."""

    def __init__(self, *scripts):
        self.scripts = list(scripts)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        script = self.scripts.pop(0)
        if isinstance(script, Exception):
            raise script
        return Stream(script)


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
    monkeypatch.setattr(runner, "make_embedder", lambda client, model: lambda t: [[0.0]])
    return found


def use_model(monkeypatch, model):
    monkeypatch.setattr("apps.providers.services.build_client", lambda *a, **k: model)
    monkeypatch.setattr("apps.providers.services.client_for", lambda user: model)


def test_agent_searches_then_answers_with_citations(db, user, agent, emb, chunks, monkeypatch):
    model = ScriptedModel(
        [delta(reasoning="Let me search. "), delta(tool_calls=tool_call("refund window"))],
        [delta("The window is 30 days "), delta("[handbook.md#0].")],
    )
    use_model(monkeypatch, model)
    events = []
    result = runner.run(
        user=user,
        agent=agent,
        messages=[{"role": "user", "content": "Refunds?"}],
        emit=events.append,
        embedding=emb,
    )
    kinds = [e["type"] for e in events]
    assert kinds == [
        "agent.thinking",
        "agent.tool_call",
        "agent.retrieval",
        "agent.token",
        "agent.token",
    ]
    assert result.answer == "The window is 30 days [handbook.md#0]."
    assert result.retrieved[0]["document"] == "handbook.md"
    assert result.mode == "agentic"
    # The second call carries the tool result, tagged so the model can cite it.
    tool_msg = model.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "[handbook.md#0]" in tool_msg["content"]
    assert "Be brief." in model.calls[0]["messages"][0]["content"]


def test_models_without_tools_fall_back_to_retrieve_then_answer(
    db, user, agent, emb, chunks, monkeypatch
):
    no_tools = BadRequestError(
        "x",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body={"error": {"message": "registry.ollama.ai/library/gemma3 does not support tools"}},
    )
    model = ScriptedModel(no_tools, [delta("30 days [handbook.md#0]")])
    use_model(monkeypatch, model)
    events = []
    result = runner.run(
        user=user,
        agent=agent,
        messages=[{"role": "user", "content": "Refunds?"}],
        emit=events.append,
        embedding=emb,
    )
    assert result.mode == "pipeline"
    assert result.answer == "30 days [handbook.md#0]"
    assert "tools" not in model.calls[1]
    assert "Passages from my documents" in model.calls[1]["messages"][-1]["content"]


def test_the_chat_picks_the_connection_and_model(db, user, agent, emb, chunks, monkeypatch):
    connection = Connection.objects.create(
        owner=user, name="Ollama", base_url="http://localhost:11434/v1"
    )
    model = ScriptedModel([delta("Hi")])
    use_model(monkeypatch, model)
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
    model = ScriptedModel([delta("Hello from the model")])
    use_model(monkeypatch, model)
    result = runner.run(
        user=user, agent=agent, messages=[{"role": "user", "content": "Hi"}], emit=lambda e: None
    )
    assert result.mode == "model" and result.answer == "Hello from the model"
    assert "tools" not in model.calls[0]  # nothing to search, so no search tool
    assert model.calls[0]["messages"][0] == {"role": "system", "content": "Be brief."}


def test_cancellation_stops_streaming(db, user, agent, emb, chunks, monkeypatch):
    model = ScriptedModel([delta("a"), delta("b"), delta("c")])
    use_model(monkeypatch, model)
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
