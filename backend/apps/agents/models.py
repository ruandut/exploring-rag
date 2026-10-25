from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

# Choices for Agent.rag_config. Kept as plain tuples so serializers, the runner and the
# frontend (features/agents/options.ts) can share the same ids.
QUERY_TRANSFORMS = ("none", "multi_query", "hyde", "step_back")
RETRIEVAL_METHODS = ("dense", "keyword", "hybrid", "mmr")
RERANKERS = ("none", "llm")
GENERATION_STRATEGIES = ("stuff", "cited", "map_reduce", "refine", "corrective")


def default_rag_config() -> dict:
    return {
        "query_transform": "none",
        "retrieval": "hybrid",
        "top_k": 5,
        "rerank": "none",
        "generation": "cited",
    }


class Agent(TimeStampedModel):
    """A configured assistant: who it is (system message), what it answers with (connection +
    model) and how it does RAG (rag_config). Folders scope what it may search (none = all)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agents"
    )
    name = models.CharField(max_length=100)
    system_message = models.TextField(blank=True)
    # None = the default provider from Settings; otherwise e.g. a local Ollama connection.
    connection = models.ForeignKey(
        "providers.Connection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agents",
    )
    model = models.CharField(max_length=200, blank=True)  # blank = the provider's chat model
    folders = models.ManyToManyField("library.Folder", blank=True, related_name="agents")
    rag_config = models.JSONField(default=default_rag_config)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="agents_agent_unique_name"),
        ]

    def __str__(self):
        return self.name
