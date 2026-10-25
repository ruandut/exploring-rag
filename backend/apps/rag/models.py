from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimeStampedModel


class ChunkingStrategy(models.TextChoices):
    FIXED = "fixed", "Fixed size"
    RECURSIVE = "recursive", "Recursive"
    MARKDOWN = "markdown", "Markdown / heading-aware"
    SEMANTIC = "semantic", "Semantic"
    PARENT_DOCUMENT = "parent_document", "Parent document"


class IndexingConfig(TimeStampedModel):
    """How a user's documents are split before embedding (spec 0004).

    Sizes are in tokens. Overlap repeats the end of one chunk at the start of the next so an
    idea cut at a boundary still appears whole in at least one chunk.
    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="indexing_config"
    )
    strategy = models.CharField(
        max_length=32, choices=ChunkingStrategy.choices, default=ChunkingStrategy.RECURSIVE
    )
    chunk_size = models.PositiveIntegerField(default=512)
    chunk_overlap = models.PositiveIntegerField(default=64)

    class Meta:
        constraints = [
            # Also validated in the serializer for a friendly message; the DB is the backstop.
            models.CheckConstraint(
                condition=models.Q(chunk_overlap__lt=models.F("chunk_size")),
                name="rag_indexing_overlap_lt_size",
            ),
        ]

    def __str__(self):
        return f"{self.owner}: {self.strategy} {self.chunk_size}/{self.chunk_overlap}"


# Dimensions that get an HNSW index (see migration 0003). Others still work, via exact search.
HNSW_DIMENSIONS = (384, 768, 1024, 1536)


class Chunk(models.Model):
    """One searchable slice of a document: text + its embedding + a full-text vector.

    Users bring their own embedding model, so `embedding` is an unsized `vector` column and
    `dimensions` says how long each one is. HNSW indexes need a fixed size, so migration 0003
    adds partial expression indexes per common size (`embedding::vector(1536)` WHERE
    dimensions = 1536). Retrieval must use the same cast to hit them.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chunks"
    )
    # rag may reference library (lower layer). Deleting a document deletes its chunks.
    document = models.ForeignKey(
        "library.Document", on_delete=models.CASCADE, related_name="chunks"
    )
    index = models.PositiveIntegerField()
    text = models.TextField()
    heading = models.CharField(max_length=500, blank=True)
    parent_text = models.TextField(blank=True)
    token_count = models.PositiveIntegerField()
    embedding = VectorField()
    dimensions = models.PositiveSmallIntegerField()
    embedding_model = models.CharField(max_length=200)
    # Postgres keeps this in sync itself; powers keyword / hybrid search (spec 0005).
    search_vector = models.GeneratedField(
        expression=SearchVector("text", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "index"]
        constraints = [
            models.UniqueConstraint(fields=["document", "index"], name="rag_chunk_unique_index"),
        ]
        indexes = [
            models.Index(fields=["owner", "dimensions"]),
            GinIndex(fields=["search_vector"], name="rag_chunk_search_gin"),
        ]

    def __str__(self):
        return f"{self.document_id}#{self.index}"
