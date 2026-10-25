"""Embeddings (spec 0010): coverage, what gets (re-)indexed, the API, and the migration."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.library import services as library_services
from apps.library.models import Document, DocumentStatus, Folder
from apps.rag import selectors, services
from apps.rag.models import Chunk, EmbeddingIndex, IndexedDocument

URL = "/api/rag/embeddings/"


@pytest.fixture(autouse=True)
def no_hatchet(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    events = []
    monkeypatch.setattr("apps.jobs.events.push_event", lambda k, p: events.append((k, p)))
    return events


@pytest.fixture
def syncs(monkeypatch):
    started = []
    monkeypatch.setattr(
        "apps.rag.services.start_sync",
        lambda index, reindex: started.append((index.pk, reindex)),
    )
    return started


def doc(user, name, folder=None):
    return library_services.upload_documents(
        user, files=[SimpleUploadedFile(name, b"text")], folder=folder
    )[0]


def emb(user, name="E", **kw):
    folders, documents = kw.pop("folders", []), kw.pop("documents", [])
    index = EmbeddingIndex.objects.create(owner=user, name=name, model="fake-embed", **kw)
    index.folders.set(folders)
    index.documents.set(documents)
    return index


def test_at_0010_02_documents_come_from_nested_folders_and_picked_files(db, user):
    policies = Folder.objects.create(owner=user, name="Policies")
    nested = Folder.objects.create(owner=user, name="Old", parent=policies)
    other = Folder.objects.create(owner=user, name="Other")
    a, b, c = doc(user, "a.md", policies), doc(user, "b.md", nested), doc(user, "c.md", other)
    loose = doc(user, "loose.md")
    index = emb(user, folders=[policies], documents=[loose])
    assert selectors.covered_document_ids(index) == {a.pk, b.pk, loose.pk}
    assert c.pk not in selectors.covered_document_ids(index)
    assert {i.pk for i in selectors.covering_embeddings(b)} == {index.pk}
    everything = emb(user, "All", all_documents=True)
    assert selectors.covered_document_ids(everything) == {a.pk, b.pk, c.pk, loose.pk}


def test_at_0010_05_adding_a_folder_indexes_only_the_new_documents(db, user):
    policies = Folder.objects.create(owner=user, name="Policies")
    support = Folder.objects.create(owner=user, name="Support")
    handbook, faq = doc(user, "handbook.md", policies), doc(user, "faq.md", support)
    index = emb(user, folders=[policies])
    assert services.plan_sync(index, reindex=False) == [handbook.pk]
    index.folders.add(support)
    assert services.plan_sync(index, reindex=False) == [faq.pk]
    assert services.plan_sync(index, reindex=True) == sorted([handbook.pk, faq.pk])


def test_at_0010_06_removing_a_folder_drops_its_chunks_but_keeps_the_document(db, user):
    support = Folder.objects.create(owner=user, name="Support")
    faq = doc(user, "faq.md", support)
    index = emb(user, folders=[support])
    services.plan_sync(index, reindex=False)
    Chunk.objects.create(
        owner=user, embedding_index=index, document=faq, index=0, text="t", token_count=1,
        embedding=[1.0], dimensions=1, embedding_model="m",
    )  # fmt: skip
    index.folders.clear()
    index.documents.add(doc(user, "other.md"))
    services.plan_sync(index, reindex=False)
    assert not Chunk.objects.filter(document=faq).exists()
    assert not IndexedDocument.objects.filter(document=faq).exists()
    assert Document.objects.filter(pk=faq.pk).exists()


def test_at_0010_07_an_upload_goes_to_every_covering_embedding(
    db, user, no_hatchet, django_capture_on_commit_callbacks
):
    policies = Folder.objects.create(owner=user, name="Policies")
    small, wide = emb(user, "Small", folders=[policies]), emb(user, "Wide", folders=[policies])
    emb(user, "Elsewhere", documents=[doc(user, "x.md")])
    with django_capture_on_commit_callbacks(execute=True):
        faq = doc(user, "faq.md", policies)
    assert ("document.uploaded", {"document_id": faq.pk, "user_id": user.pk}) in no_hatchet
    assert services.plan_document(faq.pk, reindex=False) == [small.pk, wide.pk]
    # Uploading again changes nothing; "Re-index" in the library redoes every embedding.
    assert services.plan_document(faq.pk, reindex=False) == []
    assert services.plan_document(faq.pk, reindex=True) == [small.pk, wide.pk]


def test_moves_fire_document_moved_and_update_coverage(
    db, user, no_hatchet, django_capture_on_commit_callbacks
):
    policies = Folder.objects.create(owner=user, name="Policies")
    support = Folder.objects.create(owner=user, name="Support")
    faq = doc(user, "faq.md", policies)
    index = emb(user, folders=[policies])
    services.plan_document(faq.pk, reindex=False)
    with django_capture_on_commit_callbacks(execute=True):
        library_services.move_document(faq, folder=support)
    assert ("document.moved", {"document_id": faq.pk, "user_id": user.pk}) in no_hatchet
    assert services.plan_document(faq.pk, reindex=False) == []
    assert not IndexedDocument.objects.filter(index=index, document=faq).exists()
    # Moving the folder itself under Policies brings it back.
    no_hatchet.clear()
    with django_capture_on_commit_callbacks(execute=True):
        library_services.update_folder(support, parent=policies)
    assert ("document.moved", {"document_id": faq.pk, "user_id": user.pk}) in no_hatchet
    assert services.plan_document(faq.pk, reindex=False) == [index.pk]


def test_a_document_no_embedding_covers_is_not_indexed(
    db, user, django_capture_on_commit_callbacks
):
    loose = doc(user, "loose.md")
    with django_capture_on_commit_callbacks(execute=True):
        services.plan_document(loose.pk, reindex=False)
    loose.refresh_from_db()
    assert loose.status == DocumentStatus.NOT_INDEXED


def test_at_0010_01_creating_an_embedding_starts_a_sync(
    db, user, auth_api, syncs, django_capture_on_commit_callbacks
):
    policies = Folder.objects.create(owner=user, name="Policies")
    with django_capture_on_commit_callbacks(execute=True):
        res = auth_api.post(
            URL,
            {"name": "Handbook small", "model": "fake-embed", "folders": [policies.pk]},
            format="json",
        )
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["status"] == "indexing" and body["connection_name"] == "Default provider"
    assert syncs == [(body["id"], False)]


def test_an_embedding_must_cover_something(db, auth_api):
    res = auth_api.post(URL, {"name": "Empty", "model": "fake-embed"}, format="json")
    assert res.status_code == 400 and "folders" in res.json()


def test_overlap_must_be_smaller_than_size(db, auth_api):
    res = auth_api.post(
        URL,
        {"name": "X", "model": "m", "all_documents": True, "chunk_size": 256, "chunk_overlap": 256},
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["chunk_overlap"] == ["Overlap must be smaller than the chunk size."]


def test_at_0010_08_changing_the_model_needs_confirmation_then_reindexes(
    db, user, auth_api, syncs, django_capture_on_commit_callbacks
):
    index = emb(user, all_documents=True)
    res = auth_api.patch(f"{URL}{index.pk}/", {"model": "fake-embed-16"}, format="json")
    assert res.status_code == 409 and res.json()["code"] == "reindex_required"
    index.refresh_from_db()
    assert index.model == "fake-embed"  # Cancel leaves it as it was

    with django_capture_on_commit_callbacks(execute=True):
        res = auth_api.patch(
            f"{URL}{index.pk}/", {"model": "fake-embed-16", "confirm_reindex": True}, format="json"
        )
    assert res.json()["reindex_started"] is True
    index.refresh_from_db()
    assert (index.model, index.version) == ("fake-embed-16", 2)
    assert syncs == [(index.pk, True)]


def test_renaming_or_editing_folders_needs_no_confirmation(db, user, auth_api, syncs):
    folder = Folder.objects.create(owner=user, name="F")
    index = emb(user, all_documents=True)
    res = auth_api.patch(
        f"{URL}{index.pk}/", {"name": "Renamed", "folders": [folder.pk]}, format="json"
    )
    assert res.status_code == 200 and res.json()["reindex_started"] is False


def test_embeddings_are_owner_only(db, user, other_user, auth_api):
    from rest_framework.test import APIClient

    index = emb(user, all_documents=True)
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(f"{URL}{index.pk}/").status_code == 404
    assert bob.get(URL).json() == []
    # And none of my folders can be put into Bob's embedding.
    mine = Folder.objects.create(owner=user, name="Mine")
    res = bob.post(URL, {"name": "Steal", "model": "m", "folders": [mine.pk]}, format="json")
    assert res.status_code == 400


def test_at_0010_18_deleting_an_embedding_keeps_the_documents(
    db, user, auth_api, django_capture_on_commit_callbacks
):
    handbook = doc(user, "handbook.md")
    index = emb(user, all_documents=True)
    services.plan_sync(index, reindex=False)
    with django_capture_on_commit_callbacks(execute=True):
        assert auth_api.delete(f"{URL}{index.pk}/").status_code == 204
    handbook.refresh_from_db()
    assert handbook.status == DocumentStatus.NOT_INDEXED


@pytest.mark.django_db(transaction=True)
def test_migration_moves_todays_setup_into_my_documents_without_reindexing(django_user_model):
    """0005 attaches existing chunks to "My documents" — no embedding call is made."""
    executor = MigrationExecutor(connection)
    before = [("rag", "0004_embedding_indexes"), ("providers", "0002_connection")]
    executor.migrate(before)
    old = executor.loader.project_state(before).apps
    user = django_user_model.objects.create_user("carol", password="x")
    old.get_model("providers", "ProviderConfig").objects.create(
        owner_id=user.pk, base_url="http://x/v1", chat_model="c",
        embedding_model="nomic-embed-text", embedding_dimensions=768,
    )  # fmt: skip
    old.get_model("rag", "IndexingConfig").objects.create(
        owner_id=user.pk, strategy="markdown", chunk_size=256, chunk_overlap=32
    )
    document = old.get_model("library", "Document").objects.create(
        owner_id=user.pk, name="a.md", size=1, file="x/a.md", status="ready", chunk_count=1
    )
    old.get_model("rag", "Chunk").objects.create(
        owner_id=user.pk, document=document, index=0, text="t", token_count=1,
        embedding=[0.0] * 768, dimensions=768, embedding_model="nomic-embed-text",
    )  # fmt: skip

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

    index = EmbeddingIndex.objects.get(owner=user)
    assert (index.name, index.model, index.dimensions) == ("My documents", "nomic-embed-text", 768)
    assert (index.strategy, index.chunk_size, index.chunk_overlap) == ("markdown", 256, 32)
    assert index.all_documents and index.status == "ready"
    assert Chunk.objects.get(document_id=document.pk).embedding_index == index
    assert IndexedDocument.objects.get(index=index).status == "ready"
