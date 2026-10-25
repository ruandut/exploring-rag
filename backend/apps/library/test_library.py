"""Library API: folders, uploads, permissions. Indexing itself is tested in apps/rag."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.library.models import Document, DocumentStatus, Folder


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def events(monkeypatch):
    pushed = []
    monkeypatch.setattr("apps.jobs.events.push_event", lambda k, p: pushed.append((k, p)))
    return pushed


@pytest.fixture
def bob_api(other_user):
    client = APIClient()
    client.force_authenticate(other_user)
    return client


def upload(api, *names, folder=None):
    files = [
        SimpleUploadedFile(n, b"# Hello\n\nSome text.", content_type="text/plain") for n in names
    ]
    data = {"files": files} | ({"folder": folder} if folder else {})
    return api.post("/api/library/documents/", data, format="multipart")


def test_nested_folders_are_private(auth_api, bob_api):
    projects = auth_api.post("/api/library/folders/", {"name": "Projects"}).json()
    research = auth_api.post(
        "/api/library/folders/", {"name": "Research", "parent": projects["id"]}
    ).json()
    assert research["parent"] == projects["id"]
    assert bob_api.get("/api/library/folders/").json() == []
    assert (
        bob_api.patch(f"/api/library/folders/{research['id']}/", {"name": "x"}).status_code == 404
    )
    # Bob can't create a folder inside Alice's folder either.
    res = bob_api.post("/api/library/folders/", {"name": "Sneaky", "parent": projects["id"]})
    assert res.status_code == 400


def test_duplicate_folder_names_are_rejected_per_parent(auth_api):
    auth_api.post("/api/library/folders/", {"name": "Projects"})
    res = auth_api.post("/api/library/folders/", {"name": "Projects"})
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_a_folder_cannot_move_inside_itself(auth_api):
    a = auth_api.post("/api/library/folders/", {"name": "A"}).json()
    b = auth_api.post("/api/library/folders/", {"name": "B", "parent": a["id"]}).json()
    res = auth_api.patch(f"/api/library/folders/{a['id']}/", {"parent": b["id"]}, format="json")
    assert res.status_code == 400


def test_upload_creates_queued_documents_and_announces_them(
    auth_api, user, events, django_capture_on_commit_callbacks
):
    folder = auth_api.post("/api/library/folders/", {"name": "Projects"}).json()
    with django_capture_on_commit_callbacks(execute=True):
        res = upload(auth_api, "a.md", "b.txt", folder=folder["id"])
    assert res.status_code == 201
    docs = res.json()
    assert [(d["name"], d["status"], d["folder"]) for d in docs] == [
        ("a.md", "queued", folder["id"]),
        ("b.txt", "queued", folder["id"]),
    ]
    assert events == [
        ("document.uploaded", {"document_id": d["id"], "user_id": user.id}) for d in docs
    ]


def test_unsupported_files_are_rejected(auth_api, events):
    res = upload(auth_api, "virus.exe")
    assert res.status_code == 400
    assert "unsupported type" in res.json()["detail"]
    assert Document.objects.count() == 0


def test_documents_list_filters_by_folder(auth_api, events):
    folder = auth_api.post("/api/library/folders/", {"name": "F"}).json()
    upload(auth_api, "in-folder.md", folder=folder["id"])
    upload(auth_api, "top.md")

    def names(q):
        return [d["name"] for d in auth_api.get(f"/api/library/documents/?folder={q}").json()]

    assert names(folder["id"]) == ["in-folder.md"]
    assert names("root") == ["top.md"]
    assert names("all") == ["in-folder.md", "top.md"]


def test_other_users_cannot_see_or_delete_documents(auth_api, bob_api, events):
    doc = upload(auth_api, "a.md").json()[0]
    assert bob_api.get("/api/library/documents/").json() == []
    assert bob_api.delete(f"/api/library/documents/{doc['id']}/").status_code == 404
    assert bob_api.post(f"/api/library/documents/{doc['id']}/reindex/").status_code == 404


def test_reindex_requeues_and_announces(auth_api, user, events, django_capture_on_commit_callbacks):
    doc = upload(auth_api, "a.md").json()[0]
    Document.objects.filter(pk=doc["id"]).update(status=DocumentStatus.FAILED, error="boom")
    events.clear()
    with django_capture_on_commit_callbacks(execute=True):
        res = auth_api.post(f"/api/library/documents/{doc['id']}/reindex/")
    assert res.status_code == 202
    assert res.json()["status"] == "queued" and res.json()["error"] == ""
    assert events == [
        (
            "document.reindex_requested",
            {"document_id": doc["id"], "user_id": user.id, "reindex": True},
        )
    ]


def test_moving_a_document(auth_api, events):
    doc = upload(auth_api, "a.md").json()[0]
    folder = auth_api.post("/api/library/folders/", {"name": "F"}).json()
    res = auth_api.patch(
        f"/api/library/documents/{doc['id']}/", {"folder": folder["id"]}, format="json"
    )
    assert res.json()["folder"] == folder["id"]


def test_deleting_a_folder_deletes_its_subtree(auth_api, events):
    a = auth_api.post("/api/library/folders/", {"name": "A"}).json()
    auth_api.post("/api/library/folders/", {"name": "B", "parent": a["id"]})
    upload(auth_api, "a.md", folder=a["id"])
    assert auth_api.delete(f"/api/library/folders/{a['id']}/").status_code == 204
    assert Folder.objects.count() == 0
    assert Document.objects.count() == 0
