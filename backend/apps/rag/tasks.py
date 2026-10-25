"""rag's Hatchet tasks. Auto-discovered by the worker via TASKS.

Sync functions on purpose: they use the Django ORM, and Hatchet runs sync tasks in a worker
thread. close_old_connections() keeps those threads from holding stale DB connections.
"""

from django.db import close_old_connections
from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context
from hatchet_sdk.exceptions import NonRetryableException
from pydantic import BaseModel

from apps.jobs.hatchet import get_hatchet
from apps.library import selectors as library_selectors
from apps.library import services as library_services
from apps.realtime.events import send_to_user

from . import indexing

hatchet = get_hatchet()

INDEX_RETRIES = 2


class IndexDocumentInput(BaseModel):
    document_id: int
    user_id: int


@hatchet.task(
    name="index-document",
    input_validator=IndexDocumentInput,
    # library can't import rag, so it announces uploads / re-index requests as events.
    on_events=["document.uploaded", "document.reindex_requested"],
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
        chunks = indexing.index_document(input.document_id)
        ctx.log(f"Indexed document {input.document_id}: {chunks} chunks")
        return {"chunks": chunks}
    except indexing.IndexingFailed as exc:
        indexing.mark_failed(input.document_id, str(exc))
        # Shows as failed in the Hatchet UI, without burning retries on a user error.
        raise NonRetryableException(str(exc)) from exc
    except Exception as exc:
        if ctx.retry_count >= INDEX_RETRIES:
            indexing.mark_failed(input.document_id, f"Indexing failed after retries: {exc}")
        raise
    finally:
        close_old_connections()


class ReindexInput(BaseModel):
    user_id: int
    reason: str = "provider.embedding_changed"


@hatchet.task(
    name="reindex-user-documents",
    input_validator=ReindexInput,
    # Triggered directly (chunking change) or by the event providers pushes when the
    # embedding model changes — providers can't import rag, so it announces instead.
    on_events=["provider.embedding_changed"],
    # Only the newest re-index per user matters; cancel one still running.
    concurrency=ConcurrencyExpression(
        expression="string(input.user_id)",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
    retries=2,
    backoff_factor=2.0,
)
def reindex_user_documents(input: ReindexInput, ctx: Context) -> dict:
    """Queue every document of the user again; each becomes its own index-document run."""
    close_old_connections()
    ids = library_selectors.document_ids_for(input.user_id)
    for doc_id in ids:
        doc = library_selectors.get_document_for_indexing(doc_id)
        if doc is not None:
            library_services.request_reindex(doc)
    ctx.log(f"Re-index for user {input.user_id} ({input.reason}): {len(ids)} documents queued")
    send_to_user(
        input.user_id,
        {
            "type": "job.completed",
            "run_id": ctx.workflow_run_id,
            "job": "reindex",
            "message": f"Re-index finished: {len(ids)} documents queued ({input.reason})",
        },
    )
    close_old_connections()
    return {"documents": len(ids)}


TASKS = [index_document, reindex_user_documents]
