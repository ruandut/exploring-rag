from django.db.models import QuerySet

from .models import Chunk, IndexingConfig


def get_indexing_config(user) -> IndexingConfig:
    """The user's settings, or unsaved defaults if they never changed them."""
    return IndexingConfig.objects.filter(owner=user).first() or IndexingConfig(owner=user)


def chunks_for_document(user, document_id: int) -> QuerySet[Chunk]:
    return Chunk.objects.filter(owner=user, document_id=document_id).defer("search_vector")
