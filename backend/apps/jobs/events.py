"""Hatchet events: how a lower-layer app triggers work owned by a higher-layer app.

The lower app pushes an event; the higher app's task subscribes with
`@hatchet.task(on_events=["<key>"])`. Neither imports the other.

Known event keys (keep in sync with ARCHITECTURE.md):
    document.uploaded            {"document_id", "user_id"}  library → rag: index-document
    document.reindex_requested   {"document_id", "user_id"}  library → rag: index-document
    provider.embedding_changed   {"user_id"}                 providers → rag: reindex-user-documents
"""

from django.db import transaction


def push_event(key: str, payload: dict) -> None:
    from .hatchet import get_hatchet

    get_hatchet().event.push(key, payload)


def push_event_on_commit(key: str, payload: dict) -> None:
    """Push only once the current DB transaction commits, so handlers see the saved rows."""
    transaction.on_commit(lambda: push_event(key, payload))
