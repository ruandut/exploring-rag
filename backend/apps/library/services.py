"""Write-side logic for the library: the only code that changes Folder / Document rows.

library sits below rag, so it never calls the indexer. It announces work with Hatchet events
(`document.uploaded`, `document.reindex_requested`) that rag's index-document task listens to,
and rag reports progress back through `set_status`.
"""

from pathlib import PurePath

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.jobs.events import push_event_on_commit
from apps.realtime.events import send_to_user

from .models import Document, DocumentStatus, Folder

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".txt"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


# --- folders --------------------------------------------------------------------------------


def create_folder(user, *, name: str, parent: Folder | None) -> Folder:
    if parent is not None and parent.owner_id != user.id:
        raise ValidationError("Folder not found")
    if Folder.objects.filter(owner=user, parent=parent, name=name).exists():
        raise ValidationError(f"A folder called “{name}” already exists here")
    return Folder.objects.create(owner=user, parent=parent, name=name)


def update_folder(
    folder: Folder, *, name: str | None = None, parent: Folder | None | object = ...
) -> Folder:
    if name is not None:
        folder.name = name
    if parent is not ...:
        # Moving a folder into itself or one of its descendants would create a cycle.
        node = parent
        while node is not None:
            if node.pk == folder.pk:
                raise ValidationError("A folder can't be moved inside itself")
            node = node.parent
        folder.parent = parent
    folder.save()
    return folder


@transaction.atomic
def delete_folder(folder: Folder) -> None:
    """Deletes the folder, its subfolders and their documents (chunks cascade in rag)."""
    files = [d.file for d in Document.objects.filter(folder__in=_subtree(folder))]
    folder.delete()
    transaction.on_commit(lambda: [f.delete(save=False) for f in files])


def _subtree(folder: Folder) -> list[Folder]:
    found, frontier = [folder], [folder]
    while frontier:
        frontier = list(Folder.objects.filter(parent__in=frontier))
        found.extend(frontier)
    return found


# --- documents ------------------------------------------------------------------------------


def validate_upload(uploaded) -> None:
    ext = PurePath(uploaded.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"{uploaded.name}: unsupported type. Use PDF, DOCX, Markdown or plain text."
        )
    if uploaded.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"{uploaded.name}: larger than 25 MB")


@transaction.atomic
def upload_documents(user, *, files, folder: Folder | None) -> list[Document]:
    if folder is not None and folder.owner_id != user.id:
        raise ValidationError("Folder not found")
    for f in files:
        validate_upload(f)
    documents = [
        Document.objects.create(
            owner=user,
            folder=folder,
            file=f,
            name=PurePath(f.name).name,
            content_type=getattr(f, "content_type", "") or "",
            size=f.size,
        )
        for f in files
    ]
    for doc in documents:
        push_event_on_commit("document.uploaded", {"document_id": doc.pk, "user_id": user.id})
    return documents


def move_document(document: Document, *, folder: Folder | None) -> Document:
    if folder is not None and folder.owner_id != document.owner_id:
        raise ValidationError("Folder not found")
    document.folder = folder
    document.save(update_fields=["folder", "updated_at"])
    return document


@transaction.atomic
def delete_document(document: Document) -> None:
    file = document.file
    document.delete()  # rag.Chunk rows cascade via their FK
    transaction.on_commit(lambda: file.delete(save=False))


@transaction.atomic
def request_reindex(document: Document) -> Document:
    set_status(document, DocumentStatus.QUEUED)
    push_event_on_commit(
        "document.reindex_requested", {"document_id": document.pk, "user_id": document.owner_id}
    )
    return document


def set_status(
    document: Document,
    status: DocumentStatus,
    *,
    error: str = "",
    chunk_count: int | None = None,
) -> None:
    """Update the status and tell every open tab of the owner (websocket `document.status`)."""
    document.status = status
    document.error = error
    fields = ["status", "error", "updated_at"]
    if chunk_count is not None:
        document.chunk_count = chunk_count
        fields.append("chunk_count")
    if status == DocumentStatus.READY:
        document.indexed_at = timezone.now()
        fields.append("indexed_at")
    document.save(update_fields=fields)
    payload = {
        "type": "document.status",
        "document_id": document.pk,
        "folder_id": document.folder_id,
        "status": status.value if hasattr(status, "value") else status,
        "error": error,
        "chunk_count": document.chunk_count,
    }
    transaction.on_commit(lambda: send_to_user(document.owner_id, payload))
