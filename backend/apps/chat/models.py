from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Conversation(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    # agent is None for the demo agent, or if the agent was deleted later.
    agent = models.ForeignKey(
        "agents.Agent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    agent_key = models.CharField(max_length=20)  # Agent id or "demo" — what to ask next time
    title = models.CharField(max_length=200)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user"
        ASSISTANT = "assistant"

    class Status(models.TextChoices):
        DONE = "done"
        CANCELLED = "cancelled"
        ERROR = "error"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DONE)
    run_id = models.CharField(max_length=64, blank=True)
    # Assistant messages: thinking, tool_calls, retrieved chunks, model, error — what the UI
    # showed while streaming, so a reload looks the same.
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
