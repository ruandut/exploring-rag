"""Keep an embedding's status right when its entries disappear by cascade — a document or
folder deleted in the library deletes the entries, but library can't call rag to say so."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import IndexedDocument


@receiver(post_delete, sender=IndexedDocument)
def _entry_deleted(sender, instance: IndexedDocument, **kwargs):
    from .services import refresh_index_status

    index_id = instance.index_id
    transaction.on_commit(lambda: refresh_index_status(index_id))
