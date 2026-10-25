import pytest
from rest_framework.test import APIClient


@pytest.fixture
def bob_api(other_user):
    client = APIClient()
    client.force_authenticate(other_user)
    return client


def test_create_agent_with_defaults(auth_api):
    res = auth_api.post(
        "/api/agents/", {"name": "Docs helper", "system_message": "Be nice"}, format="json"
    )
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["rag_config"] == {
        "query_transform": "none",
        "retrieval": "hybrid",
        "top_k": 5,
        "rerank": "none",
        "generation": "cited",
    }
    # Since spec 0010 the chat picks the embedding and the model, not the agent.
    assert not {"connection", "model", "folders"} & set(body)


def test_rag_options_are_validated(auth_api):
    res = auth_api.post(
        "/api/agents/", {"name": "x", "rag_config": {"retrieval": "magic"}}, format="json"
    )
    assert res.status_code == 400


def test_agents_are_private(auth_api, bob_api):
    agent = auth_api.post("/api/agents/", {"name": "Mine"}, format="json").json()
    assert bob_api.get("/api/agents/").json() == []
    assert (
        bob_api.patch(f"/api/agents/{agent['id']}/", {"name": "x"}, format="json").status_code
        == 404
    )


def test_connections_never_return_keys_and_list_models(auth_api, monkeypatch):
    res = auth_api.post(
        "/api/providers/connections/",
        {"name": "Ollama", "base_url": "http://localhost:11434/v1", "api_key": "sk-secret-9876"},
        format="json",
    )
    assert res.status_code == 201 and "sk-secret" not in res.content.decode()
    assert res.json()["api_key_last4"] == "9876"
    seen = {}

    def fake_list(base_url, api_key):
        from apps.providers.catalog import ModelInfo

        seen["key"] = api_key
        return "ollama", [ModelInfo("gemma4:e4b", "chat", "endpoint", None, True)]

    monkeypatch.setattr("apps.providers.catalog.list_models", fake_list)
    models = auth_api.get(f"/api/providers/connections/{res.json()['id']}/models/").json()
    assert [m["id"] for m in models["models"]] == ["gemma4:e4b"]
    assert seen["key"] == "sk-secret-9876"
