"""Acceptance tests for specs/0004-settings.md (indexing settings)."""

import pytest

URL = "/api/rag/indexing-config/"


@pytest.fixture
def reindexes(monkeypatch):
    started = []
    monkeypatch.setattr(
        "apps.rag.services.start_reindex", lambda user_id, reason: started.append(user_id)
    )
    return started


def test_defaults_are_returned_before_saving(auth_api):
    assert auth_api.get(URL).json() | {"updated_at": None} == {
        "strategy": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 64,
        "updated_at": None,
    }


def test_at_0004_03_overlap_must_be_smaller_than_size(auth_api):
    res = auth_api.put(
        URL, {"strategy": "fixed", "chunk_size": 256, "chunk_overlap": 256}, format="json"
    )
    assert res.status_code == 400
    assert res.json()["chunk_overlap"] == ["Overlap must be smaller than the chunk size."]


def test_at_0004_03_unknown_strategy_is_rejected(auth_api):
    res = auth_api.put(
        URL, {"strategy": "magic", "chunk_size": 256, "chunk_overlap": 0}, format="json"
    )
    assert res.status_code == 400


def test_at_0004_04_changing_chunking_needs_confirmation_then_reindexes(
    auth_api, user, reindexes, django_capture_on_commit_callbacks
):
    first = {"strategy": "recursive", "chunk_size": 512, "chunk_overlap": 64}
    assert auth_api.put(URL, first, format="json").json()["reindex_started"] is False

    changed = {**first, "chunk_size": 1024}
    res = auth_api.put(URL, changed, format="json")
    assert res.status_code == 409
    assert auth_api.get(URL).json()["chunk_size"] == 512

    with django_capture_on_commit_callbacks(execute=True):
        res = auth_api.put(URL, {**changed, "confirm_reindex": True}, format="json")
    assert res.json()["reindex_started"] is True
    assert auth_api.get(URL).json()["chunk_size"] == 1024
    assert reindexes == [user.id]
