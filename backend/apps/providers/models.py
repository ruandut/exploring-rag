from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ProviderKind(models.TextChoices):
    """Which API an endpoint speaks (spec 0008). Each kind has its own adapter in llm/."""

    OPENAI = "openai", "OpenAI-compatible"
    ANTHROPIC = "anthropic", "Anthropic"
    GOOGLE = "google", "Google"


class ProviderConfig(TimeStampedModel):
    """A user's default LLM endpoint. One per user (spec 0004); any kind since spec 0008."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_config"
    )
    kind = models.CharField(
        max_length=16, choices=ProviderKind.choices, default=ProviderKind.OPENAI
    )
    # Required for OpenAI-compatible endpoints; blank = the SDK's default for Anthropic/Google.
    base_url = models.URLField(max_length=500, blank=True)
    # Never store or return the plaintext key: see crypto.py and the serializer.
    api_key_encrypted = models.TextField(blank=True)
    api_key_last4 = models.CharField(max_length=4, blank=True)
    chat_model = models.CharField(max_length=200)
    # Embedding models live on each embedding (rag.EmbeddingIndex, spec 0010), not here.

    def __str__(self):
        return f"{self.owner} → {self.base_url}"


class Connection(TimeStampedModel):
    """An extra endpoint, e.g. a local Ollama or Claude: for chatting, and for embedding (an
    embedding names its connection, or the default provider)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connections"
    )
    name = models.CharField(max_length=100)
    kind = models.CharField(
        max_length=16, choices=ProviderKind.choices, default=ProviderKind.OPENAI
    )
    base_url = models.URLField(max_length=500, blank=True)
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
