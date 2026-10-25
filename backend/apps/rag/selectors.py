"""Read-side queries for rag. Everything a request touches is scoped to its user."""

from django.db.models import Count, Q, QuerySet

from apps.library import selectors as library_selectors

from .models import Chunk, EmbeddingIndex, IndexedDocument


def embeddings_for(user) -> QuerySet[EmbeddingIndex]:
    return (
        EmbeddingIndex.objects.filter(owner=user)
        .select_related("connection")
        .prefetch_related("folders", "documents")
        .annotate(
            total=Count("entries", distinct=True),
            done=Count(
                "entries",
                filter=Q(
                    entries__status__in=[
                        IndexedDocument.Status.READY,
                        IndexedDocument.Status.FAILED,
                    ]
                ),
                distinct=True,
            ),
        )
    )


def get_embedding(user, embedding_id: int) -> EmbeddingIndex:
    return embeddings_for(user).get(pk=embedding_id)


def get_embedding_for_task(embedding_id: int) -> EmbeddingIndex | None:
    """Used by worker tasks, which run outside any request (no user to scope by)."""
    return (
        EmbeddingIndex.objects.select_related("owner", "connection").filter(pk=embedding_id).first()
    )


def default_embedding(user) -> EmbeddingIndex | None:
    """The user's oldest embedding — what a chat searches when it hasn't picked one."""
    return EmbeddingIndex.objects.filter(owner=user).select_related("connection").first()


def covered_document_ids(index: EmbeddingIndex) -> set[int]:
    """The documents an embedding covers *now*: everything, or its folders (recursively) plus
    its picked files. Computed on demand so folder edits and moves never leave stale copies."""
    owner = index.owner
    if index.all_documents:
        return set(library_selectors.document_ids_for(owner.pk))
    folder_ids = list(index.folders.values_list("pk", flat=True))
    in_folders = (
        set(library_selectors.document_ids_in_folders(owner, folder_ids)) if folder_ids else set()
    )
    return in_folders | set(index.documents.filter(owner=owner).values_list("pk", flat=True))


def covering_embeddings(document) -> list[EmbeddingIndex]:
    """Every embedding of the document's owner that covers it."""
    ancestors: set[int] = set()
    folder = document.folder
    while folder is not None:
        ancestors.add(folder.pk)
        folder = folder.parent
    return list(
        EmbeddingIndex.objects.filter(owner_id=document.owner_id)
        .filter(Q(all_documents=True) | Q(documents=document) | Q(folders__in=ancestors))
        .select_related("owner", "connection")
        .distinct()
    )


def entries_for(index: EmbeddingIndex) -> QuerySet[IndexedDocument]:
    return IndexedDocument.objects.filter(index=index).select_related("document")


def entries_for_document(document_id: int) -> QuerySet[IndexedDocument]:
    return IndexedDocument.objects.filter(document_id=document_id).select_related("index")


def chunks_for_document(user, document_id: int, embedding_id: int | None = None) -> QuerySet[Chunk]:
    """One embedding's chunks of a document — the oldest embedding covering it by default."""
    qs = Chunk.objects.filter(owner=user, document_id=document_id).defer("search_vector")
    if embedding_id is None:
        first = qs.order_by("embedding_index__created_at", "embedding_index_id").first()
        if first is None:
            return qs.none()
        embedding_id = first.embedding_index_id
    return qs.filter(embedding_index_id=embedding_id).select_related("embedding_index")


def chunk_count(index: EmbeddingIndex, document_id: int | None = None) -> int:
    qs = Chunk.objects.filter(embedding_index=index)
    if document_id is not None:
        qs = qs.filter(document_id=document_id)
    return qs.count()
