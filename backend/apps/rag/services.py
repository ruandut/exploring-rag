from django.db import transaction

from .models import IndexingConfig
from .selectors import get_indexing_config

CHUNKING_FIELDS = ("strategy", "chunk_size", "chunk_overlap")


class ReindexConfirmationRequired(Exception):
    """Saving would change how documents are chunked; the caller must confirm a re-index."""


def start_reindex(user_id: int, reason: str) -> None:
    from .tasks import ReindexInput, reindex_user_documents

    reindex_user_documents.run_no_wait(ReindexInput(user_id=user_id, reason=reason))


@transaction.atomic
def save_indexing_config(user, *, data: dict, confirm_reindex: bool) -> tuple[IndexingConfig, bool]:
    config = get_indexing_config(user)
    changed = config.pk is not None and any(
        data[k] != getattr(config, k) for k in CHUNKING_FIELDS if k in data
    )
    if changed and not confirm_reindex:
        raise ReindexConfirmationRequired

    for field in CHUNKING_FIELDS:
        if field in data:
            setattr(config, field, data[field])
    config.save()
    if changed:
        transaction.on_commit(lambda: start_reindex(user.id, "chunking settings changed"))
    return config, changed
