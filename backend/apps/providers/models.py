from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ProviderConfig(TimeStampedModel):
    """A user's OpenAI-compatible LLM endpoint. One per user (spec 0004)."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_config"
    )
    base_url = models.URLField(max_length=500)
    # Never store or return the plaintext key: see crypto.py and the serializer.
    api_key_encrypted = models.TextField(blank=True)
    api_key_last4 = models.CharField(max_length=4, blank=True)
    chat_model = models.CharField(max_length=200)
    embedding_model = models.CharField(max_length=200)
    # Vector size the embedding model returns. Detected by "Test connection"; spec 0003 uses it
    # for the pgvector column.
    embedding_dimensions = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.owner} → {self.base_url}"


class Connection(TimeStampedModel):
    """An extra OpenAI-compatible endpoint an agent can use for chat, e.g. a local Ollama.

    The default ProviderConfig stays responsible for embeddings (every chunk must be embedded
    by the same model); connections only add more choices for answering.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connections"
    )
    name = models.CharField(max_length=100)
    base_url = models.URLField(max_length=500)
    api_key_encrypted = models.TextField(blank=True)
    api_key_last4 = models.CharField(max_length=4, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="providers_connection_unique_name"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.base_url})"
