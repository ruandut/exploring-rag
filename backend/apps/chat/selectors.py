from django.db.models import Count, QuerySet

from .models import Conversation, Message

HISTORY_LIMIT = 20  # messages sent back to the model as context


def conversations_for(user) -> QuerySet[Conversation]:
    return (
        Conversation.objects.filter(owner=user)
        .select_related("agent")
        .annotate(message_count=Count("messages"))
    )


def get_conversation(user, conversation_id: int) -> Conversation:
    return Conversation.objects.select_related("agent").get(owner=user, pk=conversation_id)


def history(conversation: Conversation) -> list[dict]:
    """The recent turns as OpenAI-style messages (only ones with text)."""
    rows = list(
        Message.objects.filter(conversation=conversation)
        .exclude(content="")
        .order_by("-created_at", "-pk")
        .values("role", "content")[:HISTORY_LIMIT]
    )
    return list(reversed(rows))
