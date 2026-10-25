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


class EmbeddingIndex(TimeStampedModel):
    """A named embedding of some of the user's documents (spec 0010).

    One index = one embedding model + one chunking setting over a set of documents (folders,
    picked files, or everything). Every vector in it comes from that one model — vectors from
    different models (or of different sizes) can't be compared — so retrieval always searches
    one index at a time and embeds the query with that index's model. Several indexes may cover
    the same documents, which is what lets you compare "small chunks + model A" with
    "large chunks + model B".
    """

    class Status(models.TextChoices):
        INDEXING = "indexing", "Indexing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="embedding_indexes"
    )
    name = models.CharField(max_length=100)
    # None = the default provider from Settings. PROTECT: deleting a connection an index still
    # embeds with would leave its vectors unreproducible (queries couldn't be embedded).
    connection = models.ForeignKey(
        "providers.Connection",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="embedding_indexes",
    )
    model = models.CharField(max_length=200)
    # Filled in from the model picker, or by the first embedding call when left empty.
    dimensions = models.PositiveIntegerField(null=True, blank=True)
    strategy = models.CharField(
        max_length=32, choices=ChunkingStrategy.choices, default=ChunkingStrategy.RECURSIVE
    )
    chunk_size = models.PositiveIntegerField(default=512)  # tokens
    chunk_overlap = models.PositiveIntegerField(default=64)
    # What it covers: everything in the library, or the union of these folders (with their
    # subfolders) and these single files. Resolved when needed, never copied.
    all_documents = models.BooleanField(default=False)
    folders = models.ManyToManyField("library.Folder", blank=True, related_name="+")
    documents = models.ManyToManyField("library.Document", blank=True, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INDEXING)
    error = models.TextField(blank=True)
    # Bumped by every full re-index. An index-document run started for an older version
    # throws its result away, so a slow run with the old model can't overwrite new vectors.
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="rag_index_unique_name"),
            models.CheckConstraint(
                condition=models.Q(chunk_overlap__lt=models.F("chunk_size")),
                name="rag_index_overlap_lt_size",
            ),
        ]

    def __str__(self):
        return self.name


class IndexedDocument(models.Model):
    """One document's state inside one index. The library shows a document's worst state
    across all the indexes that cover it."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        INDEXING = "indexing", "Indexing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    index = models.ForeignKey(EmbeddingIndex, on_delete=models.CASCADE, related_name="entries")
    document = models.ForeignKey(
        "library.Document", on_delete=models.CASCADE, related_name="index_entries"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    error = models.TextField(blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["index", "document"]
        constraints = [
            models.UniqueConstraint(fields=["index", "document"], name="rag_entry_unique"),
        ]

    def __str__(self):
        return f"{self.index_id}:{self.document_id} {self.status}"


class ParsedText(models.Model):
    """A document's extracted text. Parsing (PDF/DOCX → text) doesn't depend on the index, so
    it runs once per document however many indexes chunk and embed it."""

    document = models.OneToOneField(
        "library.Document", on_delete=models.CASCADE, related_name="parsed_text"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"text of {self.document_id}"


# Dimensions that get an HNSW index (see migration 0003). Others still work, via exact search.
HNSW_DIMENSIONS = (384, 768, 1024, 1536)


class Chunk(models.Model):
    """One searchable slice of a document: text + its embedding + a full-text vector.

    Users bring their own embedding models, so `embedding` is an unsized `vector` column and
    `dimensions` says how long each one is. HNSW indexes need a fixed size, so migration 0003
    adds partial expression indexes per common size (`embedding::vector(1536)` WHERE
    dimensions = 1536). Retrieval must use the same cast to hit them.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chunks"
    )
    # Which embedding this vector belongs to. Retrieval filters on it, so two indexes of the
    # same model and size never mix.
    embedding_index = models.ForeignKey(
        EmbeddingIndex, on_delete=models.CASCADE, related_name="chunks"
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
        ordering = ["embedding_index", "document", "index"]
        constraints = [
            models.UniqueConstraint(
                fields=["embedding_index", "document", "index"], name="rag_chunk_unique_index"
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "dimensions"]),
            models.Index(fields=["embedding_index", "dimensions"]),
            GinIndex(fields=["search_vector"], name="rag_chunk_search_gin"),
        ]

    def __str__(self):
        return f"{self.document_id}#{self.index}"
