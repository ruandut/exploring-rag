"""Acceptance tests for specs/0004-settings.md (LLM provider)."""

import pytest
from rest_framework.test import APIClient

from apps.providers import services
from apps.providers.llm import ProviderError
from apps.providers.llm.testing import FakeAdapter
from apps.providers.models import ProviderConfig
from apps.providers.selectors import get_api_key

URL = "/api/providers/config/"

PROVIDER = {
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-test-1234567890abcd",
    "chat_model": "gpt-test",
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


def use(monkeypatch, adapter=None, seen=None):
    def build(kind, base_url, api_key, **kwargs):
        if seen is not None:
            seen.update(kind=kind, key=api_key)
        return adapter or FakeAdapter()

    monkeypatch.setattr(services, "build_adapter", build)


def test_at_0004_02_test_connection_reports_success(auth_api, monkeypatch):
    use(monkeypatch)
    res = auth_api.post("/api/providers/test/", PROVIDER, format="json")
    body = res.json()
    assert body["ok"] is True and body["chat"]["ok"]
    # Embeddings have their own Test now (spec 0010), on the embedding form.
    assert "embeddings" not in body


def test_at_0004_02_test_connection_shows_the_provider_error(auth_api, monkeypatch):
    use(monkeypatch, FakeAdapter(error=ProviderError("Incorrect API key provided", permanent=True)))
    body = auth_api.post("/api/providers/test/", PROVIDER, format="json").json()
    assert body["ok"] is False
    assert body["chat"]["detail"] == "Incorrect API key provided"


def test_at_0004_02_test_connection_falls_back_to_the_saved_key(auth_api, monkeypatch):
    auth_api.put(URL, PROVIDER, format="json")
    seen = {}
    use(monkeypatch, seen=seen)
    auth_api.post("/api/providers/test/", {**PROVIDER, "api_key": ""}, format="json")
    assert seen["key"] == PROVIDER["api_key"]


def test_saving_the_provider_never_reindexes(auth_api, pushed_events):
    """Embedding models live on each embedding now (spec 0010): nothing to re-index here."""
    auth_api.put(URL, PROVIDER, format="json")
    res = auth_api.put(URL, {**PROVIDER, "base_url": "https://other.example.com/v1"}, format="json")
    assert res.status_code == 200
    assert pushed_events == []


def test_test_embedding_reports_the_dimensions():
    body = services.test_embedding(adapter=FakeAdapter(embed_dims=768), model="nomic-embed-text")
    assert body["ok"] is True and body["dimensions"] == 768
    failing = FakeAdapter(error=ProviderError("Incorrect API key provided", permanent=True))
    body = services.test_embedding(adapter=failing, model="x")
    assert (body["ok"], body["detail"]) == (False, "Incorrect API key provided")


def test_at_0008_01_test_connection_works_for_every_kind(auth_api, monkeypatch):
    seen = {}
    use(monkeypatch, seen=seen)
    body = auth_api.post(
        "/api/providers/test/",
        {"kind": "anthropic", "chat_model": "claude-opus-5-5"},
        format="json",
    ).json()
    assert body["ok"] is True and seen["kind"] == "anthropic"


def test_openai_compatible_needs_a_base_url_but_claude_does_not(auth_api):
    res = auth_api.put(URL, {"kind": "openai", "chat_model": "m"}, format="json")
    assert res.status_code == 400 and "base_url" in res.json()
    res = auth_api.put(
        URL,
        {"kind": "anthropic", "api_key": "sk-ant-x", "chat_model": "claude-opus-5-5"},
        format="json",
    )
    assert res.status_code == 200 and res.json()["kind"] == "anthropic"
