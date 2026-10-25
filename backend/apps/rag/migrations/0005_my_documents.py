"""Move today's single embedding into a named one, with no re-index (spec 0010).

Before 0010 every user had one embedding: the default provider's embedding model, the
IndexingConfig chunking, over all documents. That becomes an embedding called "My documents"
covering all documents, and every existing chunk (and document state) is attached to it — no
embedding calls, so nothing is re-indexed.
"""

from django.db import migrations

DEFAULTS = {"strategy": "recursive", "chunk_size": 512, "chunk_overlap": 64}


def forwards(apps, schema_editor):
    ProviderConfig = apps.get_model("providers", "ProviderConfig")
    IndexingConfig = apps.get_model("rag", "IndexingConfig")
    EmbeddingIndex = apps.get_model("rag", "EmbeddingIndex")
    IndexedDocument = apps.get_model("rag", "IndexedDocument")
    Chunk = apps.get_model("rag", "Chunk")
    Document = apps.get_model("library", "Document")

    chunking = {
        c.owner_id: {
            "strategy": c.strategy,
            "chunk_size": c.chunk_size,
            "chunk_overlap": c.chunk_overlap,
        }
        for c in IndexingConfig.objects.all()
    }
    for provider in ProviderConfig.objects.all():
        owner_id = provider.owner_id
        documents = list(Document.objects.filter(owner_id=owner_id))
        failed = [d for d in documents if d.status == "failed"]
        index = EmbeddingIndex.objects.create(
            owner_id=owner_id,
            name="My documents",
            connection=None,
            model=provider.embedding_model,
            dimensions=provider.embedding_dimensions,
            all_documents=True,
            status="failed" if failed else "ready",
            error=f"{failed[0].name}: {failed[0].error}" if failed else "",
            **chunking.get(owner_id, DEFAULTS),
        )
        Chunk.objects.filter(owner_id=owner_id).update(embedding_index=index)
        IndexedDocument.objects.bulk_create(
            IndexedDocument(
                index=index,
                document=d,
                # A document that was mid-indexing stays queued; re-index it from the page.
                status=d.status if d.status in ("ready", "failed") else "queued",
                error=d.error,
                chunk_count=d.chunk_count,
                indexed_at=d.indexed_at,
            )
            for d in documents
        )
    # Chunks of users without a provider can't belong to any embedding.
    Chunk.objects.filter(embedding_index__isnull=True).delete()
    Document.objects.exclude(owner_id__in=ProviderConfig.objects.values("owner_id")).update(
        status="not_indexed", chunk_count=0
    )


class Migration(migrations.Migration):
    dependencies = [
        ("rag", "0004_embedding_indexes"),
        ("providers", "0002_connection"),
        ("library", "0002_not_indexed_status"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
