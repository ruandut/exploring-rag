"""The indexing pipeline for one document in one embedding: parse → chunk → embed → store.

Called by the `index-document` Hatchet task. Everything a user can fix (no provider, bad key,
unreadable file, wrong dimensions) raises IndexingFailed with a message for the UI and is not
retried. Anything else (network blips, rate limits, provider 5xx) propagates so Hatchet retries.

Parsing doesn't depend on the embedding, so its result is cached per document (ParsedText):
three embeddings of one PDF parse it once and chunk + embed it three times.
"""

from django.db import transaction
from openai import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    UnprocessableEntityError,
)

from apps.library import selectors as library_selectors
from apps.providers import services as provider_services

from . import selectors, services
from .chunking import chunk
from .embedding import make_embedder
from .models import Chunk, EmbeddingIndex, IndexedDocument, ParsedText
from .parsing import ParseError, parse

PERMANENT_PROVIDER_ERRORS = (
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)


class IndexingFailed(Exception):
    """A problem the user must fix; retrying won't help."""


def parsed_text(doc) -> str:
    cached = ParsedText.objects.filter(document=doc).first()
    if cached is not None:
        return cached.text
    with doc.file.open("rb") as fh:
        data = fh.read()
    try:
        text = parse(doc.name, data)
    except ParseError as exc:
        raise IndexingFailed(str(exc)) from exc
    ParsedText.objects.update_or_create(document=doc, defaults={"text": text})
    return text


def index_document(index_id: int, document_id: int, version: int) -> int:
    """Index (or re-index) one document into one embedding. Returns the chunks stored."""
    index = selectors.get_embedding_for_task(index_id)
    doc = library_selectors.get_document_for_indexing(document_id)
    if index is None or doc is None or index.version != version:
        return 0  # deleted, or re-indexed again while queued: a newer run does the work
    services.set_entry_status(index_id, document_id, IndexedDocument.Status.INDEXING)

    try:
        client = provider_services.embedding_client(index.owner, index.connection)
    except ValueError as exc:
        raise IndexingFailed(f"{exc} — add one in Settings.") from exc
    text = parsed_text(doc)

    embed = make_embedder(client, index.model)
    try:
        drafts = chunk(
            text,
            strategy=index.strategy,
            size=index.chunk_size,
            overlap=index.chunk_overlap,
            embed=embed,
        )
        # The heading path is embedded with the text so "Install" under "Setup" is findable
        # by either word; the stored text stays clean.
        vectors = embed([f"{d.heading}\n\n{d.text}" if d.heading else d.text for d in drafts])
    except PERMANENT_PROVIDER_ERRORS as exc:
        raise IndexingFailed(provider_services.error_message(exc)) from exc

    dims = len(vectors[0]) if vectors else index.dimensions or 0
    if index.dimensions and dims and dims != index.dimensions:
        raise IndexingFailed(
            f"The embedding model returned {dims} dimensions, but the embedding says "
            f"{index.dimensions}. Fix it and re-index."
        )

    with transaction.atomic():
        current = EmbeddingIndex.objects.select_for_update().filter(pk=index_id).first()
        if current is None or current.version != version:
            return 0  # changed while we were embedding — these vectors are already stale
        if not current.dimensions and dims:
            # First vectors decide the size when the user left it empty.
            EmbeddingIndex.objects.filter(pk=index_id).update(dimensions=dims)
        # Re-indexing replaces everything; old vectors aren't comparable with new ones.
        Chunk.objects.filter(embedding_index_id=index_id, document=doc).delete()
        Chunk.objects.bulk_create(
            Chunk(
                owner=doc.owner,
                embedding_index_id=index_id,
                document=doc,
                index=i,
                text=d.text,
                heading=d.heading[:500],
                parent_text=d.parent_text,
                token_count=d.token_count,
                embedding=vector,
                dimensions=dims,
                embedding_model=index.model,
            )
            for i, (d, vector) in enumerate(zip(drafts, vectors, strict=True))
        )
        services.set_entry_status(
            index_id, document_id, IndexedDocument.Status.READY, chunk_count=len(drafts)
        )
    return len(drafts)


def mark_failed(index_id: int, document_id: int, message: str) -> None:
    services.set_entry_status(
        index_id, document_id, IndexedDocument.Status.FAILED, error=message[:2000]
    )
