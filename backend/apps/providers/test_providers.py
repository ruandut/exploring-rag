"""Acceptance tests for specs/0004-settings.md (LLM provider)."""

from types import SimpleNamespace

import pytest
from openai import AuthenticationError
from rest_framework.test import APIClient

from apps.providers import services
from apps.providers.models import ProviderConfig
from apps.providers.selectors import get_api_key

URL = "/api/providers/config/"

PROVIDER = {
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-test-1234567890abcd",
    "chat_model": "gpt-test",
    "embedding_model": "embed-test",
    "embedding_dimensions": 1536,
}


@pytest.fixture
def pushed_events(monkeypatch):
    events = []
    monkeypatch.setattr("apps.jobs.events.push_event", lambda k, p: events.append((k, p)))
    return events


def test_at_0004_01_api_never_returns_the_key(auth_api, user):
    res = auth_api.put(URL, PROVIDER, format="json")
    assert res.status_code == 200
    assert "sk-test" not in res.content.decode()
    assert res.json()["api_key_last4"] == "abcd"
    assert res.json()["has_api_key"] is True

    get = auth_api.get(URL)
    assert "sk-test" not in get.content.decode()
    assert "api_key" not in get.json()


def test_at_0004_01_key_is_encrypted_at_rest(auth_api, user):
    auth_api.put(URL, PROVIDER, format="json")
    stored = ProviderConfig.objects.get(owner=user)
    assert "sk-test" not in stored.api_key_encrypted
    assert get_api_key(stored) == PROVIDER["api_key"]


def test_at_0004_01_omitting_the_key_keeps_it(auth_api, user):
    auth_api.put(URL, PROVIDER, format="json")
    without_key = {k: v for k, v in PROVIDER.items() if k != "api_key"}
    auth_api.put(URL, {**without_key, "chat_model": "gpt-3"}, format="json")
    stored = ProviderConfig.objects.get(owner=user)
    assert stored.chat_model == "gpt-3"
    assert get_api_key(stored) == PROVIDER["api_key"]


def test_provider_config_is_per_user(auth_api, other_user):
    auth_api.put(URL, PROVIDER, format="json")
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(URL).status_code == 204


class FakeClient:
    def __init__(self, *, fail_chat=None, fail_embed=None):
        self.fail_chat, self.fail_embed = fail_chat, fail_embed
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._embed)

    def _chat(self, **kwargs):
        if self.fail_chat:
            raise self.fail_chat
        msg = SimpleNamespace(content="OK")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def _embed(self, **kwargs):
        if self.fail_embed:
            raise self.fail_embed
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * 768)])


def _auth_error(message):
    response = SimpleNamespace(status_code=401, headers={}, request=None)
    return AuthenticationError(message, response=response, body={"error": {"message": message}})


def test_at_0004_02_test_connection_reports_success(auth_api, monkeypatch):
    monkeypatch.setattr(services, "build_client", lambda *a, **k: FakeClient())
    res = auth_api.post("/api/providers/test/", PROVIDER, format="json")
    body = res.json()
    assert body["ok"] is True
    assert body["chat"]["ok"] and body["embeddings"]["ok"]
    assert body["embedding_dimensions"] == 768


def test_at_0004_02_test_connection_shows_the_provider_error(auth_api, monkeypatch):
    err = _auth_error("Incorrect API key provided")
    monkeypatch.setattr(services, "build_client", lambda *a, **k: FakeClient(fail_chat=err))
    body = auth_api.post("/api/providers/test/", PROVIDER, format="json").json()
    assert body["ok"] is False
    assert body["chat"]["detail"] == "Incorrect API key provided"
    assert body["embeddings"]["ok"] is True


def test_at_0004_02_test_connection_falls_back_to_the_saved_key(auth_api, monkeypatch):
    auth_api.put(URL, PROVIDER, format="json")
    seen = {}

    def fake_build(base_url, api_key, **kwargs):
        seen["key"] = api_key
        return FakeClient()

    monkeypatch.setattr(services, "build_client", fake_build)
    auth_api.post("/api/providers/test/", {**PROVIDER, "api_key": ""}, format="json")
    assert seen["key"] == PROVIDER["api_key"]


def test_at_0004_04_changing_embedding_model_needs_confirmation(
    auth_api, pushed_events, django_capture_on_commit_callbacks
):
    auth_api.put(URL, PROVIDER, format="json")
    changed = {**PROVIDER, "embedding_model": "embed-v2"}

    res = auth_api.put(URL, changed, format="json")
    assert res.status_code == 409
    assert res.json()["code"] == "reindex_required"
    assert ProviderConfig.objects.get().embedding_model == "embed-test"

    with django_capture_on_commit_callbacks(execute=True):
        res = auth_api.put(URL, {**changed, "confirm_reindex": True}, format="json")
    assert res.status_code == 200
    assert res.json()["reindex_started"] is True
    assert ProviderConfig.objects.get().embedding_model == "embed-v2"
    assert pushed_events == [("provider.embedding_changed", {"user_id": res.wsgi_request.user.id})]


def test_at_0004_04_other_changes_dont_reindex(auth_api, pushed_events):
    auth_api.put(URL, PROVIDER, format="json")
    res = auth_api.put(URL, {**PROVIDER, "chat_model": "gpt-other"}, format="json")
    assert res.status_code == 200
    assert res.json()["reindex_started"] is False
    assert pushed_events == []
