"""The indexing pipeline for one document: parse → chunk → embed → store.

Called by the `index-document` Hatchet task. Everything a user can fix (no provider, bad key,
unreadable file, wrong dimensions) raises IndexingFailed with a message for the UI and is not
retried. Anything else (network blips, rate limits, provider 5xx) propagates so Hatchet retries.
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
from apps.library import services as library_services
from apps.library.models import DocumentStatus
from apps.providers import selectors as provider_selectors
from apps.providers import services as provider_services

from .chunking import chunk
from .embedding import make_embedder
from .models import Chunk
from .parsing import ParseError, parse
from .selectors import get_indexing_config

PERMANENT_PROVIDER_ERRORS = (
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)


class IndexingFailed(Exception):
    """A problem the user must fix; retrying won't help."""


def index_document(document_id: int) -> int:
    """Index (or re-index) one document. Returns the number of chunks stored."""
    doc = library_selectors.get_document_for_indexing(document_id)
    if doc is None:
        return 0  # deleted while queued
    owner = doc.owner
    library_services.set_status(doc, DocumentStatus.INDEXING)

    provider = provider_selectors.get_provider_config(owner)
    if provider is None:
        raise IndexingFailed("No LLM provider configured — add one in Settings.")
    config = get_indexing_config(owner)

    with doc.file.open("rb") as fh:
        data = fh.read()
    try:
        text = parse(doc.name, data)
    except ParseError as exc:
        raise IndexingFailed(str(exc)) from exc

    embed = make_embedder(provider_services.client_for(owner), provider.embedding_model)
    try:
        drafts = chunk(
            text,
            strategy=config.strategy,
            size=config.chunk_size,
            overlap=config.chunk_overlap,
            embed=embed,
        )
        # The heading path is embedded with the text so "Install" under "Setup" is findable
        # by either word; the stored text stays clean.
        vectors = embed([f"{d.heading}\n\n{d.text}" if d.heading else d.text for d in drafts])
    except PERMANENT_PROVIDER_ERRORS as exc:
        raise IndexingFailed(provider_services.error_message(exc)) from exc

    dims = len(vectors[0])
    if provider.embedding_dimensions and dims != provider.embedding_dimensions:
        raise IndexingFailed(
            f"The embedding model returned {dims} dimensions, but Settings says "
            f"{provider.embedding_dimensions}. Fix the setting and re-index."
        )

    with transaction.atomic():
        # Re-indexing replaces everything; old vectors aren't comparable with new ones.
        Chunk.objects.filter(document=doc).delete()
        Chunk.objects.bulk_create(
            Chunk(
                owner=owner,
                document=doc,
                index=i,
                text=d.text,
                heading=d.heading[:500],
                parent_text=d.parent_text,
                token_count=d.token_count,
                embedding=vector,
                dimensions=dims,
                embedding_model=provider.embedding_model,
            )
            for i, (d, vector) in enumerate(zip(drafts, vectors, strict=True))
        )
        library_services.set_status(doc, DocumentStatus.READY, chunk_count=len(drafts))
    return len(drafts)


def mark_failed(document_id: int, message: str) -> None:
    doc = library_selectors.get_document_for_indexing(document_id)
    if doc is not None:
        library_services.set_status(doc, DocumentStatus.FAILED, error=message[:2000])
