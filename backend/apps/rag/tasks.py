"""rag's Hatchet tasks. Auto-discovered by the worker via TASKS.

    document.uploaded / .moved / .reindex_requested ──▶ route-document ─┐
    create / edit / re-index an embedding ──────────▶ sync-embedding ──┴─▶ index-document × N
                                                                          (one per document
                                                                           per embedding)

Sync functions on purpose: they use the Django ORM, and Hatchet runs sync tasks in a worker
thread. close_old_connections() keeps those threads from holding stale DB connections.
"""

from django.db import close_old_connections
from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context
from hatchet_sdk.exceptions import NonRetryableException
from pydantic import BaseModel

from apps.jobs.hatchet import get_hatchet

from . import indexing, selectors, services

hatchet = get_hatchet()

INDEX_RETRIES = 2


class IndexDocumentInput(BaseModel):
    index_id: int
    document_id: int
    user_id: int
    version: int  # the embedding's version when queued; stale runs do nothing


@hatchet.task(
    name="index-document",
    input_validator=IndexDocumentInput,
    retries=INDEX_RETRIES,
    backoff_factor=2.0,
    execution_timeout="10m",
    # Up to 3 documents per user at once; other users' uploads interleave fairly.
    concurrency=ConcurrencyExpression(
        expression="string(input.user_id)",
        max_runs=3,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    ),
)
def index_document(input: IndexDocumentInput, ctx: Context) -> dict:
    close_old_connections()
    try:
        chunks = indexing.index_document(input.index_id, input.document_id, input.version)
        ctx.log(f"Indexed document {input.document_id} in {input.index_id}: {chunks} chunks")
        return {"chunks": chunks}
    except indexing.IndexingFailed as exc:
        indexing.mark_failed(input.index_id, input.document_id, str(exc))
        # Shows as failed in the Hatchet UI, without burning retries on a user error.
        raise NonRetryableException(str(exc)) from exc
    except Exception as exc:
        if ctx.retry_count >= INDEX_RETRIES:
            indexing.mark_failed(
                input.index_id, input.document_id, f"Indexing failed after retries: {exc}"
            )
        raise
    finally:
        close_old_connections()


def _queue(index_id: int, document_ids: list[int]) -> None:
    index = selectors.get_embedding_for_task(index_id)
    if index is None:
        return
    for document_id in document_ids:
        index_document.run_no_wait(
            IndexDocumentInput(
                index_id=index_id,
                document_id=document_id,
                user_id=index.owner_id,
                version=index.version,
            )
        )


class RouteDocumentInput(BaseModel):
    document_id: int
    user_id: int
    reindex: bool = False  # true for "Re-index" in the library: every covering embedding


@hatchet.task(
    name="route-document",
    input_validator=RouteDocumentInput,
    # library can't import rag, so it announces uploads, moves and re-index requests as
    # events; this task works out which embeddings cover the document now.
    on_events=["document.uploaded", "document.moved", "document.reindex_requested"],
    retries=2,
    backoff_factor=2.0,
)
def route_document(input: RouteDocumentInput, ctx: Context) -> dict:
    close_old_connections()
    try:
        to_index = services.plan_document(input.document_id, reindex=input.reindex)
        for index_id in to_index:
            _queue(index_id, [input.document_id])
        ctx.log(f"Document {input.document_id} → embeddings {to_index or 'none'}")
        return {"embeddings": to_index}
    finally:
        close_old_connections()


class SyncEmbeddingInput(BaseModel):
    index_id: int
    user_id: int
    reindex: bool = False


@hatchet.task(
    name="sync-embedding",
    input_validator=SyncEmbeddingInput,
    # One at a time per embedding, in order: two quick edits must not interleave.
    concurrency=ConcurrencyExpression(
        expression="string(input.index_id)",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    ),
    retries=2,
    backoff_factor=2.0,
)
def sync_embedding(input: SyncEmbeddingInput, ctx: Context) -> dict:
    """Match the embedding's entries to what it covers and queue what needs (re-)indexing."""
    close_old_connections()
    try:
        index = selectors.get_embedding_for_task(input.index_id)
        if index is None:
            return {"documents": 0}
        to_index = services.plan_sync(index, reindex=input.reindex)
        _queue(index.pk, to_index)
        ctx.log(f"Embedding {index.pk} ({'re-index' if input.reindex else 'sync'}): {to_index}")
        return {"documents": len(to_index)}
    finally:
        close_old_connections()


TASKS = [index_document, route_document, sync_embedding]
