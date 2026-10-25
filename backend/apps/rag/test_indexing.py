"""The indexing pipeline with a fake OpenAI client (no network, no Hatchet)."""

from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openai import AuthenticationError

from apps.library import services as library_services
from apps.library.models import Document, DocumentStatus
from apps.providers.models import ProviderConfig
from apps.rag import indexing
from apps.rag.models import Chunk, IndexingConfig


@pytest.fixture(autouse=True)
def media(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.setattr("apps.jobs.events.push_event", lambda k, p: None)


class FakeEmbeddings:
    def __init__(self, dims=8, error=None):
        self.dims, self.error, self.calls = dims, error, []

    def create(self, model, input):
        if self.error:
            raise self.error
        self.calls.append(len(input))
        data = [SimpleNamespace(index=i, embedding=[0.1] * self.dims) for i in range(len(input))]
        return SimpleNamespace(data=list(reversed(data)))  # out of order on purpose


@pytest.fixture
def fake_client(monkeypatch):
    embeddings = FakeEmbeddings()
    monkeypatch.setattr(
        "apps.providers.services.client_for", lambda user: SimpleNamespace(embeddings=embeddings)
    )
    return embeddings


@pytest.fixture
def provider(user):
    return ProviderConfig.objects.create(
        owner=user,
        base_url="http://fake/v1",
        chat_model="c",
        embedding_model="fake-embed",
        embedding_dimensions=8,
    )


def make_doc(user, name="handbook.md", body=b"# Policies\n\nThe refund window is 30 days."):
    return library_services.upload_documents(
        user, files=[SimpleUploadedFile(name, body)], folder=None
    )[0]


def test_indexing_stores_chunks_with_embeddings(db, user, provider, fake_client):
    IndexingConfig.objects.create(owner=user, strategy="markdown", chunk_size=512, chunk_overlap=64)
    doc = make_doc(user)
    assert indexing.index_document(doc.pk) == 1
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.READY and doc.chunk_count == 1 and doc.indexed_at
    chunk = Chunk.objects.get(document=doc)
    assert chunk.text == "The refund window is 30 days."
    assert chunk.heading == "Policies"
    assert chunk.dimensions == 8 and len(chunk.embedding) == 8
    assert chunk.embedding_model == "fake-embed"


def test_full_text_search_vector_is_generated(db, user, provider, fake_client):
    doc = make_doc(user)
    indexing.index_document(doc.pk)
    assert Chunk.objects.filter(document=doc, search_vector="refunds").exists()  # stemmed


def test_embeddings_are_batched(db, user, provider, fake_client, monkeypatch):
    monkeypatch.setattr("apps.rag.embedding.BATCH_SIZE", 2)
    IndexingConfig.objects.create(owner=user, strategy="fixed", chunk_size=64, chunk_overlap=0)
    doc = make_doc(user, "big.txt", (" ".join(f"w{i}" for i in range(300))).encode())
    assert indexing.index_document(doc.pk) == 5
    assert fake_client.calls == [2, 2, 1]
    assert list(Chunk.objects.filter(document=doc).values_list("index", flat=True)) == [
        0,
        1,
        2,
        3,
        4,
    ]


def test_reindexing_replaces_old_chunks(db, user, provider, fake_client):
    doc = make_doc(user)
    indexing.index_document(doc.pk)
    indexing.index_document(doc.pk)
    assert Chunk.objects.filter(document=doc).count() == 1


def test_no_provider_is_a_user_error(db, user, fake_client):
    doc = make_doc(user)
    with pytest.raises(indexing.IndexingFailed, match="No LLM provider"):
        indexing.index_document(doc.pk)


def test_auth_errors_are_not_retried(db, user, provider, fake_client):
    response = SimpleNamespace(status_code=401, headers={}, request=None)
    fake_client.error = AuthenticationError(
        "nope", response=response, body={"error": {"message": "Incorrect API key provided"}}
    )
    doc = make_doc(user)
    with pytest.raises(indexing.IndexingFailed, match="Incorrect API key provided"):
        indexing.index_document(doc.pk)


def test_dimension_mismatch_is_reported(db, user, provider, fake_client):
    fake_client.dims = 4
    doc = make_doc(user)
    with pytest.raises(indexing.IndexingFailed, match="returned 4 dimensions"):
        indexing.index_document(doc.pk)


def test_unreadable_files_fail_with_a_reason(db, user, provider, fake_client):
    doc = make_doc(user, "scan.pdf", b"not really a pdf")
    with pytest.raises(indexing.IndexingFailed, match="PDF"):
        indexing.index_document(doc.pk)


def test_mark_failed_records_the_message(db, user):
    doc = make_doc(user)
    indexing.mark_failed(doc.pk, "Incorrect API key provided")
    doc.refresh_from_db()
    assert (doc.status, doc.error) == (DocumentStatus.FAILED, "Incorrect API key provided")


def test_deleting_a_document_deletes_its_chunks(db, user, provider, fake_client):
    doc = make_doc(user)
    indexing.index_document(doc.pk)
    library_services.delete_document(doc)
    assert not Document.objects.exists() and not Chunk.objects.exists()


def test_chunks_endpoint_is_owner_only(db, user, other_user, provider, fake_client, auth_api):
    from rest_framework.test import APIClient

    doc = make_doc(user)
    indexing.index_document(doc.pk)
    body = auth_api.get(f"/api/rag/documents/{doc.pk}/chunks/").json()
    assert body[0]["dimensions"] == 8 and len(body[0]["embedding_preview"]) == 6
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(f"/api/rag/documents/{doc.pk}/chunks/").status_code == 404
