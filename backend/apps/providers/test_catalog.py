"""The model picker's catalogue (spec 0010): which models embed, which chat, and how we know."""

from types import SimpleNamespace

import pytest

from apps.providers import catalog
from apps.providers.llm import make_adapter

_LISTED: dict = {}


class FakeModels:
    def __init__(self, ids, extra=None):
        self.items = [SimpleNamespace(id=i, model_extra=(extra or {}).get(i, {})) for i in ids]

    def list(self):
        return self.items


def fake_endpoint(monkeypatch, *, ids, ollama=None, extra=None):
    """ids: what GET /models lists. ollama: {model: /api/show body} makes it an Ollama."""
    _LISTED["models"] = FakeModels(ids, extra)

    def fake_json(url, body=None):
        if ollama is None:
            raise catalog.EndpointError("404")
        if url.endswith("/api/version"):
            return {"version": "0.12.0"}
        return ollama[body["model"]]

    monkeypatch.setattr(catalog, "_json", fake_json)


def _adapter(base_url: str):
    """An OpenAI-compatible adapter whose /models listing is the fake one."""
    adapter = make_adapter("openai", base_url, "k", timeout=1)
    adapter.client = SimpleNamespace(models=_LISTED["models"])
    return adapter


def by_id(payload):
    return {m["id"]: m for m in payload["models"]}


def test_at_0010_10_ollama_metadata_decides_kind_and_dimensions(monkeypatch):
    fake_endpoint(
        monkeypatch,
        ids=["fake-chat", "fake-embed", "fake-notools"],
        ollama={
            "fake-embed": {
                "capabilities": ["embedding"],
                "model_info": {"bert.embedding_length": 8},
            },
            "fake-chat": {"capabilities": ["completion", "tools"]},
            "fake-notools": {"capabilities": ["completion"]},
        },
    )
    everything = by_id(catalog.catalogue(_adapter("http://localhost:11434/v1"), want=None))
    assert everything["fake-embed"] == {
        "id": "fake-embed",
        "kind": "embedding",
        "source": "endpoint",
        "dimensions": 8,
        "tools": None,
    }
    assert everything["fake-chat"]["tools"] is True
    assert everything["fake-notools"]["tools"] is False
    embeddings = catalog.catalogue(_adapter("http://localhost:11434/v1"), want="embedding")
    assert [m["id"] for m in embeddings["models"]] == ["fake-embed"]
    assert embeddings["endpoint"] == "ollama" and embeddings["hint"] == ""


def test_at_0010_11_table_then_name_then_unknown(monkeypatch):
    fake_endpoint(monkeypatch, ids=["acme-embed-small", "mystery-7b", "nomic-embed-text:latest"])
    models = by_id(catalog.catalogue(_adapter("http://bare.example/v1"), want="embedding"))
    assert models["nomic-embed-text:latest"]["source"] == "known"
    assert models["nomic-embed-text:latest"]["dimensions"] == 768
    assert (models["acme-embed-small"]["kind"], models["acme-embed-small"]["source"]) == (
        "embedding",
        "guessed",
    )
    # A model nobody can classify is always listed — a wrong guess must never hide it.
    assert models["mystery-7b"]["kind"] == "unknown"


def test_chat_lists_hide_embedding_models(monkeypatch):
    fake_endpoint(monkeypatch, ids=["text-embedding-3-small", "gpt-5-mini", "mystery-7b"])
    ids = [
        m["id"]
        for m in catalog.catalogue(_adapter("https://api.openai.com/v1"), want="chat")["models"]
    ]
    assert ids == ["gpt-5-mini", "mystery-7b"]


@pytest.mark.parametrize(
    ("base_url", "ollama", "hint"),
    [
        ("http://localhost:11434/v1", {}, "ollama pull nomic-embed-text"),
        ("https://openrouter.ai/api/v1", None, "OpenRouter has no embedding models"),
    ],
)
def test_at_0010_12_no_embedding_models_shows_how_to_get_one(monkeypatch, base_url, ollama, hint):
    fake_endpoint(monkeypatch, ids=[], ollama=ollama)
    assert hint in catalog.catalogue(_adapter(base_url), want="embedding")["hint"]


def test_openrouter_modalities(monkeypatch):
    fake_endpoint(
        monkeypatch,
        ids=["a/chat", "b/embed"],
        extra={
            "a/chat": {"architecture": {"output_modalities": ["text"]}},
            "b/embed": {"architecture": {"output_modalities": ["embeddings"]}},
        },
    )
    models = by_id(catalog.catalogue(_adapter("https://openrouter.ai/api/v1"), want=None))
    assert models["a/chat"]["kind"] == "chat" and models["b/embed"]["kind"] == "embedding"


def test_model_lists_are_owner_only(db, user, other_user, auth_api):
    from rest_framework.test import APIClient

    from apps.providers.models import Connection

    conn = Connection.objects.create(owner=user, name="Mine", base_url="http://x/v1")
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(f"/api/providers/connections/{conn.pk}/models/").status_code == 404
