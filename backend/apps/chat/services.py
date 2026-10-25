from dataclasses import dataclass, field

from django.db import transaction

from apps.agents import selectors as agent_selectors
from apps.agents.models import Agent
from apps.agents.services import DEMO_AGENT

from . import selectors
from .models import Conversation, Message


class UnknownTarget(Exception):
    """The agent or conversation doesn't exist (or isn't the user's)."""


@transaction.atomic
def begin_turn(
    user, *, agent_key: str, conversation_id: int | None, text: str
) -> tuple[Conversation, list[dict]]:
    """Store the user's message (starting a conversation if needed) and return the history to
    send to the agent, ending with that message."""
    agent = None
    if agent_key != DEMO_AGENT:
        try:
            agent = agent_selectors.get_agent(user, int(agent_key))
        except (Agent.DoesNotExist, ValueError) as exc:
            raise UnknownTarget("Unknown agent") from exc

    if conversation_id:
        try:
            conversation = selectors.get_conversation(user, int(conversation_id))
        except (Conversation.DoesNotExist, ValueError) as exc:
            raise UnknownTarget("Unknown conversation") from exc
        conversation.agent, conversation.agent_key = agent, agent_key
    else:
        conversation = Conversation(owner=user, agent=agent, agent_key=agent_key, title=text[:200])
    conversation.save()

    Message.objects.create(conversation=conversation, role=Message.Role.USER, content=text)
    return conversation, selectors.history(conversation)


@dataclass
class ReplyAccumulator:
    """Collects the streamed agent.* events into what gets saved."""

    text: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    model: str = ""
    error: str = ""
    finished: bool = False

    def add(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "agent.token":
            self.text += event.get("text", "")
        elif kind == "agent.thinking":
            self.thinking += event.get("text", "")
        elif kind == "agent.tool_call":
            self.tool_calls.append({"tool": event.get("tool"), "args": event.get("args", {})})
        elif kind == "agent.retrieval":
            self.retrieved.extend(event.get("chunks", []))
        elif kind == "agent.done":
            self.model = event.get("model", "")
            self.finished = True
        elif kind == "agent.error":
            self.error = event.get("detail", "Unknown error")


def save_reply(
    conversation_id: int, *, run_id: str, reply: ReplyAccumulator, cancelled: bool
) -> Message:
    if cancelled:
        status = Message.Status.CANCELLED
    elif reply.error or not reply.finished:
        status = Message.Status.ERROR
    else:
        status = Message.Status.DONE
    message = Message.objects.create(
        conversation_id=conversation_id,
        role=Message.Role.ASSISTANT,
        content=reply.text,
        status=status,
        run_id=run_id,
        metadata={
            "thinking": reply.thinking,
            "tool_calls": reply.tool_calls,
            "retrieved": reply.retrieved,
            "model": reply.model,
            "error": reply.error
            or ("" if status != Message.Status.ERROR else "The run ended unexpectedly"),
        },
    )
    Conversation.objects.filter(pk=conversation_id).update(updated_at=message.created_at)
    return message
