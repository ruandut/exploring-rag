"""Write-side logic for embeddings: the only code that changes EmbeddingIndex / IndexedDocument
rows (Chunk rows are written by indexing.py).

    create / edit an embedding ──▶ sync-embedding task ──▶ one index-document run per document
    library event (upload, move, re-index) ──▶ route-document task ──▶ the same runs

Every state change is pushed to the browser as `embedding.status` (per embedding) and
`document.status` (the document's worst state across the embeddings that cover it).
"""

from django.db import transaction
from django.utils import timezone

from apps.library import selectors as library_selectors
from apps.library import services as library_services
from apps.library.models import DocumentStatus
from apps.realtime.events import send_to_user

from . import selectors
from .models import Chunk, EmbeddingIndex, IndexedDocument

# Changing any of these makes every stored vector of the embedding wrong: full re-index.
REINDEX_FIELDS = ("connection", "model", "dimensions", "strategy", "chunk_size", "chunk_overlap")
COVERAGE_FIELDS = ("all_documents", "folders", "documents")

# Worst first: a document is "failed" if any embedding failed it, and so on.
_SEVERITY = [
    IndexedDocument.Status.FAILED,
    IndexedDocument.Status.INDEXING,
    IndexedDocument.Status.QUEUED,
    IndexedDocument.Status.READY,
]


class ReindexConfirmationRequired(Exception):
    """Saving would change how this embedding's vectors are made; the caller must confirm."""


# --- embeddings ---------------------------------------------------------------------------


@transaction.atomic
def create_embedding(user, *, data: dict) -> EmbeddingIndex:
    index = EmbeddingIndex(owner=user, status=EmbeddingIndex.Status.INDEXING)
    _apply(index, data)
    index.save()
    _apply_coverage(index, data)
    transaction.on_commit(lambda: start_sync(index, reindex=False))
    return index


@transaction.atomic
def update_embedding(
    index: EmbeddingIndex, *, data: dict, confirm_reindex: bool
) -> tuple[EmbeddingIndex, bool]:
    """Returns (index, reindex_started). Coverage edits only index the difference."""
    reindex = any(
        field in data and _value(data[field]) != _value(getattr(index, field))
        for field in REINDEX_FIELDS
    )
    if reindex and not confirm_reindex:
        raise ReindexConfirmationRequired
    coverage = any(field in data for field in COVERAGE_FIELDS)

    _apply(index, data)
    if reindex:
        index.version += 1
        index.status = EmbeddingIndex.Status.INDEXING
    index.save()
    _apply_coverage(index, data)
    if reindex:
        # The old vectors came from another model or chunking; keeping any would mix them.
        Chunk.objects.filter(embedding_index=index).delete()
        IndexedDocument.objects.filter(index=index).update(
            status=IndexedDocument.Status.QUEUED, chunk_count=0, error=""
        )
    if reindex or coverage:
        transaction.on_commit(lambda: start_sync(index, reindex=reindex))
    return index, reindex


@transaction.atomic
def reindex_embedding(index: EmbeddingIndex) -> None:
    """Rebuild every vector of the embedding (same settings), e.g. after fixing a key."""
    index.version += 1
    index.status = EmbeddingIndex.Status.INDEXING
    index.error = ""
    index.save(update_fields=["version", "status", "error", "updated_at"])
    IndexedDocument.objects.filter(index=index).update(status=IndexedDocument.Status.QUEUED)
    transaction.on_commit(lambda: start_sync(index, reindex=True))


@transaction.atomic
def delete_embedding(index: EmbeddingIndex) -> None:
    """Deletes the embedding and its vectors. The documents stay in the library."""
    document_ids = list(index.entries.values_list("document_id", flat=True))
    index.delete()
    transaction.on_commit(lambda: [refresh_document_status(d) for d in document_ids])


def start_sync(index: EmbeddingIndex, *, reindex: bool) -> None:
    from .tasks import SyncEmbeddingInput, sync_embedding

    sync_embedding.run_no_wait(
        SyncEmbeddingInput(index_id=index.pk, user_id=index.owner_id, reindex=reindex)
    )


def _value(v):
    # FK fields arrive as model instances; compare by id.
    return getattr(v, "pk", v)


def _apply(index: EmbeddingIndex, data: dict) -> None:
    for field in ("name", "connection", *REINDEX_FIELDS[1:], "all_documents"):
        if field in data:
            setattr(index, field, data[field])


def _apply_coverage(index: EmbeddingIndex, data: dict) -> None:
    if "folders" in data:
        index.folders.set(data["folders"])
    if "documents" in data:
        index.documents.set(data["documents"])


# --- which documents an embedding needs to (re-)index -----------------------------------------


@transaction.atomic
def plan_sync(index: EmbeddingIndex, *, reindex: bool) -> list[int]:
    """Make the embedding's entries match what it covers. Returns the documents to index:
    all of them on a re-index, otherwise only the newly covered ones."""
    covered = selectors.covered_document_ids(index)
    existing = dict(IndexedDocument.objects.filter(index=index).values_list("document_id", "pk"))
    removed = set(existing) - covered
    if removed:
        Chunk.objects.filter(embedding_index=index, document_id__in=removed).delete()
        IndexedDocument.objects.filter(index=index, document_id__in=removed).delete()
    added = covered - set(existing)
    # ignore_conflicts: an upload's route-document may be adding the same entry right now.
    IndexedDocument.objects.bulk_create(
        (IndexedDocument(index=index, document_id=d) for d in sorted(added)),
        ignore_conflicts=True,
    )
    to_index = sorted(covered) if reindex else sorted(added)
    if to_index:
        IndexedDocument.objects.filter(index=index, document_id__in=to_index).update(
            status=IndexedDocument.Status.QUEUED, error=""
        )
    transaction.on_commit(lambda: _after_sync(index.pk, removed | set(to_index)))
    return to_index


def _after_sync(index_id: int, touched: set[int]) -> None:
    refresh_index_status(index_id)
    for document_id in touched:
        refresh_document_status(document_id)


@transaction.atomic
def plan_document(document_id: int, *, reindex: bool) -> list[int]:
    """A document was uploaded, moved or asked to be re-indexed: return the embeddings that
    must index it, and drop it from embeddings that no longer cover it."""
    document = library_selectors.get_document_for_indexing(document_id)
    if document is None:
        return []
    covering = {i.pk for i in selectors.covering_embeddings(document)}
    existing = set(
        IndexedDocument.objects.filter(document=document).values_list("index_id", flat=True)
    )
    for index_id in existing - covering:
        Chunk.objects.filter(embedding_index_id=index_id, document=document).delete()
        IndexedDocument.objects.filter(index_id=index_id, document=document).delete()
    IndexedDocument.objects.bulk_create(
        (IndexedDocument(index_id=i, document=document) for i in sorted(covering - existing)),
        ignore_conflicts=True,  # a sync-embedding run may be adding it at the same moment
    )
    to_index = sorted(covering) if reindex else sorted(covering - existing)
    IndexedDocument.objects.filter(document=document, index_id__in=to_index).update(
        status=IndexedDocument.Status.QUEUED, error=""
    )
    changed = (existing - covering) | set(to_index)
    transaction.on_commit(
        lambda: (
            [refresh_index_status(i) for i in changed],
            refresh_document_status(document_id),
        )
    )
    return to_index


# --- per-document progress (called by indexing.py) -------------------------------------------


def set_entry_status(
    index_id: int,
    document_id: int,
    status: str,
    *,
    error: str = "",
    chunk_count: int | None = None,
) -> None:
    updates: dict = {"status": status, "error": error}
    if chunk_count is not None:
        updates["chunk_count"] = chunk_count
    if status == IndexedDocument.Status.READY:
        updates["indexed_at"] = timezone.now()
    IndexedDocument.objects.filter(index_id=index_id, document_id=document_id).update(**updates)
    transaction.on_commit(
        lambda: (refresh_index_status(index_id), refresh_document_status(document_id))
    )


@transaction.atomic
def refresh_index_status(index_id: int) -> None:
    """Recompute an embedding's status from its entries and push `embedding.status`."""
    # Lock the row: index-document runs finish concurrently and each recomputes this.
    index = EmbeddingIndex.objects.select_for_update().filter(pk=index_id).first()
    if index is None:
        return
    entries = list(IndexedDocument.objects.filter(index=index).select_related("document"))
    statuses = {e.status for e in entries}
    failed = [e for e in entries if e.status == IndexedDocument.Status.FAILED]
    if statuses & {IndexedDocument.Status.QUEUED, IndexedDocument.Status.INDEXING}:
        status, error = EmbeddingIndex.Status.INDEXING, ""
    elif failed:
        first = failed[0]
        others = f" (and {len(failed) - 1} more)" if len(failed) > 1 else ""
        status, error = (
            EmbeddingIndex.Status.FAILED,
            f"{first.document.name}: {first.error}{others}",
        )
    else:
        status, error = EmbeddingIndex.Status.READY, ""
    if (index.status, index.error) != (status, error):
        index.status, index.error = status, error
        index.save(update_fields=["status", "error", "updated_at"])
    done = sum(
        1
        for e in entries
        if e.status in (IndexedDocument.Status.READY, IndexedDocument.Status.FAILED)
    )
    payload = {
        "type": "embedding.status",
        "embedding_id": index.pk,
        "status": status,
        "done": done,
        "total": len(entries),
        "error": error,
    }
    transaction.on_commit(lambda: send_to_user(index.owner_id, payload))


def refresh_document_status(document_id: int) -> None:
    """The library shows one status per document: its worst across the embeddings covering
    it, or "Not indexed" when none does."""
    document = library_selectors.get_document_for_indexing(document_id)
    if document is None:
        return
    entries = list(selectors.entries_for_document(document_id))
    if not entries:
        status, error, chunks = DocumentStatus.NOT_INDEXED, "", 0
    else:
        worst = min(entries, key=lambda e: _SEVERITY.index(e.status))
        status = DocumentStatus(worst.status)
        error = (
            f"{worst.index.name}: {worst.error}"
            if len(entries) > 1 and worst.error
            else worst.error
        )
        chunks = max(e.chunk_count for e in entries)
    if (document.status, document.error, document.chunk_count) == (status, error, chunks):
        return
    library_services.set_status(document, status, error=error[:2000], chunk_count=chunks)
