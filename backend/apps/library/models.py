import uuid
from pathlib import PurePath

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Folder(TimeStampedModel):
    """A user's folder. `parent=None` means top level ("All documents" is the virtual root)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="folders"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "parent", "name"],
                name="library_folder_unique_name_per_parent",
                nulls_distinct=False,  # two top-level folders can't share a name either
            ),
        ]

    def __str__(self):
        return self.name


def _upload_path(instance: Document, filename: str) -> str:
    # A random directory per upload so two files with the same name never collide.
    return f"documents/{instance.owner_id}/{uuid.uuid4().hex}/{PurePath(filename).name}"


class DocumentStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    INDEXING = "indexing", "Indexing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"
    # No embedding covers the document (spec 0010), so nothing searches it yet.
    NOT_INDEXED = "not_indexed", "Not indexed"


class Document(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents"
    )
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.CASCADE, related_name="documents"
    )
    file = models.FileField(upload_to=_upload_path, max_length=500)
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=16, choices=DocumentStatus.choices, default=DocumentStatus.QUEUED
    )
    error = models.TextField(blank=True)
    # Written by rag when indexing finishes; denormalised so the list view needs no join.
    chunk_count = models.PositiveIntegerField(default=0)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["owner", "folder"])]

    def __str__(self):
        return self.name

    @property
    def extension(self) -> str:
        return PurePath(self.name).suffix.lower()
