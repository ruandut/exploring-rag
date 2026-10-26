"""The indexing pipeline with a fake OpenAI client (no network, no Hatchet)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.library import services as library_services
from apps.library.models import Document, DocumentStatus
from apps.providers.llm import ProviderError
from apps.providers.llm.testing import FakeAdapter
from apps.providers.models import ProviderConfig
from apps.rag import indexing, services
from apps.rag.models import Chunk, EmbeddingIndex, IndexedDocument, ParsedText


@pytest.fixture(autouse=True)
def media(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr("apps.jobs.events.push_event", lambda k, p: None)


@pytest.fixture
def fake_client(monkeypatch):
    """The embedding provider, whatever its kind: a fake adapter (8-dimensional vectors)."""
    adapter = FakeAdapter()
    monkeypatch.setattr("apps.providers.services.build_adapter", lambda *a, **k: adapter)
    return adapter


@pytest.fixture
def provider(user):
    return ProviderConfig.objects.create(owner=user, base_url="http://fake/v1", chat_model="c")


@pytest.fixture
def emb(user):
    """An embedding of everything, using the default provider."""
    return EmbeddingIndex.objects.create(
        owner=user, name="All", model="fake-embed", dimensions=8, all_documents=True
    )


def make_doc(user, name="handbook.md", body=b"# Policies\n\nThe refund window is 30 days."):
    return library_services.upload_documents(
        user, files=[SimpleUploadedFile(name, body)], folder=None
    )[0]


def index(emb, doc):
    """What the route-document task does for an upload, then the index-document run."""
    services.plan_document(doc.pk, reindex=False)
    emb.refresh_from_db()
    return indexing.index_document(emb.pk, doc.pk, emb.version)


def test_indexing_stores_chunks_with_embeddings(
    db, user, provider, emb, fake_client, django_capture_on_commit_callbacks
):
    EmbeddingIndex.objects.filter(pk=emb.pk).update(strategy="markdown")
    emb.refresh_from_db()
    doc = make_doc(user)
    with django_capture_on_commit_callbacks(execute=True):
        assert index(emb, doc) == 1
    doc.refresh_from_db()
    emb.refresh_from_db()
    assert emb.status == EmbeddingIndex.Status.READY
    assert doc.status == DocumentStatus.READY and doc.chunk_count == 1 and doc.indexed_at
    chunk = Chunk.objects.get(document=doc)
    assert chunk.text == "The refund window is 30 days."
    assert chunk.heading == "Policies"
    assert chunk.dimensions == 8 and len(chunk.embedding) == 8
    assert chunk.embedding_model == "fake-embed" and chunk.embedding_index == emb


def test_full_text_search_vector_is_generated(db, user, provider, emb, fake_client):
    doc = make_doc(user)
    index(emb, doc)
    assert Chunk.objects.filter(document=doc, search_vector="refunds").exists()  # stemmed


def test_embeddings_are_batched(db, user, provider, emb, fake_client, monkeypatch):
    monkeypatch.setattr("apps.rag.embedding.BATCH_SIZE", 2)
    EmbeddingIndex.objects.filter(pk=emb.pk).update(
        strategy="fixed", chunk_size=64, chunk_overlap=0
    )
    emb.refresh_from_db()
    doc = make_doc(user, "big.txt", (" ".join(f"w{i}" for i in range(300))).encode())
    assert index(emb, doc) == 5
    assert fake_client.embedded == [2, 2, 1]
    assert list(Chunk.objects.filter(document=doc).values_list("index", flat=True)) == [
        0,
        1,
        2,
        3,
        4,
    ]


def test_reindexing_replaces_old_chunks(db, user, provider, emb, fake_client):
    doc = make_doc(user)
    index(emb, doc)
    index(emb, doc)
    assert Chunk.objects.filter(document=doc).count() == 1


def test_parsing_happens_once_per_document(db, user, provider, emb, fake_client, monkeypatch):
    other = EmbeddingIndex.objects.create(owner=user, name="Other", model="m", all_documents=True)
    doc = make_doc(user)
    services.plan_document(doc.pk, reindex=False)
    calls = []
    real = indexing.parse
    monkeypatch.setattr(indexing, "parse", lambda *a: calls.append(a) or real(*a))
    indexing.index_document(emb.pk, doc.pk, emb.version)
    indexing.index_document(other.pk, doc.pk, other.version)
    assert len(calls) == 1 and ParsedText.objects.filter(document=doc).exists()
    # Each embedding has its own chunks of the same document.
    assert Chunk.objects.filter(document=doc).count() == 2


def test_a_stale_run_never_overwrites_newer_vectors(db, user, provider, emb, fake_client):
    doc = make_doc(user)
    services.plan_document(doc.pk, reindex=False)
    old_version = emb.version
    EmbeddingIndex.objects.filter(pk=emb.pk).update(version=old_version + 1)
    assert indexing.index_document(emb.pk, doc.pk, old_version) == 0
    assert not Chunk.objects.exists()


def test_no_provider_is_a_user_error(db, user, emb):
    doc = make_doc(user)
    with pytest.raises(indexing.IndexingFailed, match="No LLM provider"):
        index(emb, doc)


def test_auth_errors_are_not_retried(db, user, provider, emb, fake_client):
    fake_client.error = ProviderError("Incorrect API key provided", permanent=True)
    doc = make_doc(user)
    with pytest.raises(indexing.IndexingFailed, match="Incorrect API key provided"):
        index(emb, doc)


def test_dimension_mismatch_is_reported(db, user, provider, emb, fake_client):
    fake_client.embed_dims = 4
    doc = make_doc(user)
    with pytest.raises(indexing.IndexingFailed, match="returned 4 dimensions"):
        index(emb, doc)


def test_empty_dimensions_are_filled_in_by_the_first_vectors(db, user, provider, emb, fake_client):
    EmbeddingIndex.objects.filter(pk=emb.pk).update(dimensions=None)
    emb.refresh_from_db()
    index(emb, make_doc(user))
    emb.refresh_from_db()
    assert emb.dimensions == 8


def test_unreadable_files_fail_with_a_reason(db, user, provider, emb, fake_client):
    doc = make_doc(user, "scan.pdf", b"not really a pdf")
    with pytest.raises(indexing.IndexingFailed, match="PDF"):
        index(emb, doc)


def test_mark_failed_records_the_message(db, user, emb, django_capture_on_commit_callbacks):
    doc = make_doc(user)
    with django_capture_on_commit_callbacks(execute=True):
        services.plan_document(doc.pk, reindex=False)
        indexing.mark_failed(emb.pk, doc.pk, "Incorrect API key provided")
    doc.refresh_from_db()
    emb.refresh_from_db()
    assert (doc.status, doc.error) == (DocumentStatus.FAILED, "Incorrect API key provided")
    assert emb.status == EmbeddingIndex.Status.FAILED
    assert emb.error == "handbook.md: Incorrect API key provided"


def test_deleting_a_document_deletes_its_chunks(db, user, provider, emb, fake_client):
    doc = make_doc(user)
    index(emb, doc)
    library_services.delete_document(doc)
    assert not Document.objects.exists() and not Chunk.objects.exists()
    assert not IndexedDocument.objects.exists()


def test_chunks_endpoint_is_owner_only(db, user, other_user, provider, emb, fake_client, auth_api):
    from rest_framework.test import APIClient

    doc = make_doc(user)
    index(emb, doc)
    body = auth_api.get(f"/api/rag/documents/{doc.pk}/chunks/").json()
    assert body[0]["dimensions"] == 8 and len(body[0]["embedding_preview"]) == 6
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(f"/api/rag/documents/{doc.pk}/chunks/").status_code == 404


def test_transient_provider_errors_are_retried(db, user, provider, emb, fake_client):
    fake_client.error = ProviderError("Rate limited", permanent=False)
    with pytest.raises(ProviderError):  # not IndexingFailed: Hatchet retries it
        index(emb, make_doc(user))
