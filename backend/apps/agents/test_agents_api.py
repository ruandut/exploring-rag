import pytest
from rest_framework.test import APIClient

from apps.library.models import Folder
from apps.providers.models import Connection


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
    assert body["connection"] is None and body["folders"] == []


def test_rag_options_are_validated(auth_api):
    res = auth_api.post(
        "/api/agents/", {"name": "x", "rag_config": {"retrieval": "magic"}}, format="json"
    )
    assert res.status_code == 400


def test_a_connection_needs_a_model(auth_api, user):
    conn = Connection.objects.create(
        owner=user, name="Ollama", base_url="http://localhost:11434/v1"
    )
    res = auth_api.post("/api/agents/", {"name": "Local", "connection": conn.pk}, format="json")
    assert res.status_code == 400 and "model" in res.json()
    res = auth_api.post(
        "/api/agents/",
        {"name": "Local", "connection": conn.pk, "model": "gemma4:e4b"},
        format="json",
    )
    assert res.status_code == 201 and res.json()["connection_name"] == "Ollama"


def test_other_users_folders_and_connections_are_rejected(auth_api, other_user):
    theirs = Folder.objects.create(owner=other_user, name="Theirs")
    conn = Connection.objects.create(owner=other_user, name="C", base_url="http://x/v1")
    assert (
        auth_api.post(
            "/api/agents/", {"name": "a", "folders": [theirs.pk]}, format="json"
        ).status_code
        == 400
    )
    res = auth_api.post(
        "/api/agents/", {"name": "b", "connection": conn.pk, "model": "m"}, format="json"
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
        seen["key"] = api_key
        return ["gemma4:e4b", "gemma4:12b"]

    monkeypatch.setattr("apps.providers.services.list_models", fake_list)
    models = auth_api.get(f"/api/providers/connections/{res.json()['id']}/models/").json()
    assert models == {"models": ["gemma4:e4b", "gemma4:12b"]}
    assert seen["key"] == "sk-secret-9876"
