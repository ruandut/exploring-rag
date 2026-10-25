import logging
from dataclasses import dataclass, field

from django.db import transaction

from apps.agents import selectors as agent_selectors
from apps.agents.models import Agent
from apps.agents.services import DEMO_AGENT
from apps.realtime.events import send_to_user

from . import selectors
from .models import Conversation, Message

log = logging.getLogger(__name__)


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


def mark_run_started(conversation_id: int, run_id: str) -> bool:
    """Remember which run is answering. False if the conversation was deleted meanwhile."""
    return bool(Conversation.objects.filter(pk=conversation_id).update(active_run_id=run_id))


def cancel_run(run_id: str) -> None:
    from apps.jobs.hatchet import get_hatchet

    get_hatchet().runs.cancel(run_id)


def delete_conversation(user, conversation_id: int) -> None:
    """Delete one of the user's conversations and its messages (FK cascade).

    A reply still streaming is cancelled first: in Hatchet (so the worker stops calling the
    LLM) and on the socket relaying it (so the browser sees agent.cancelled straight away).
    Raises Conversation.DoesNotExist for someone else's conversation — the view turns that
    into a 404.
    """
    conversation = selectors.get_conversation(user, conversation_id)
    if run_id := conversation.active_run_id:
        try:
            cancel_run(run_id)
        except Exception:  # noqa: BLE001 - a dead Hatchet mustn't block deleting
            log.exception("Couldn't cancel run %s", run_id)
        send_to_user(
            user.pk, {"type": "agent.cancelled", "run_id": run_id}, cancel_background=run_id
        )
    conversation.delete()


@transaction.atomic
def save_reply(
    conversation_id: int, *, run_id: str, reply: ReplyAccumulator, cancelled: bool
) -> Message | None:
    """Store the finished (or stopped) reply. None if the conversation was deleted meanwhile."""
    # Lock the row so a concurrent delete waits for us (and then cascades our message too)
    # instead of us inserting a message for a conversation that's already gone.
    conversation = Conversation.objects.select_for_update().filter(pk=conversation_id).first()
    if conversation is None:
        return None
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
    Conversation.objects.filter(pk=conversation_id).update(
        updated_at=message.created_at, active_run_id=""
    )
    return message
