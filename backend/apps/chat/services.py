import logging
from dataclasses import dataclass, field

from django.db import transaction

from apps.agents import selectors as agent_selectors
from apps.agents.models import Agent
from apps.agents.services import DEMO_AGENT
from apps.providers import selectors as provider_selectors
from apps.providers.models import Connection
from apps.rag import selectors as rag_selectors
from apps.rag.models import EmbeddingIndex
from apps.realtime.events import send_to_user

from . import selectors
from .models import Conversation, Message

log = logging.getLogger(__name__)


class UnknownTarget(Exception):
    """The agent, embedding, connection or conversation doesn't exist (or isn't the user's)."""


KEEP = object()  # "not sent": keep what the conversation already uses


@dataclass
class RunSettings:
    """What answers this turn: chosen in the chat, stored on the conversation."""

    embedding_id: int | None
    connection_id: int | None
    model: str
    agent_name: str
    embedding: dict | None  # {"id", "name", "model", "dimensions"} — saved on the reply


@transaction.atomic
def begin_turn(
    user,
    *,
    agent_key: str,
    conversation_id: int | None,
    text: str,
    embedding_id=KEEP,
    connection_id=KEEP,
    model=KEEP,
) -> tuple[Conversation, list[dict], RunSettings]:
    """Store the user's message (starting a conversation if needed) and return the history to
    send to the agent, ending with that message, plus what answers it.

    embedding_id / connection_id / model change the conversation's choice from this message
    on (spec 0010); left out, the conversation keeps its own (a new one: the oldest
    embedding and the default provider). embedding_id None = search nothing."""
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
        if embedding_id is KEEP:
            default = rag_selectors.default_embedding(user)
            conversation.embedding = default
            conversation.embedding_name = default.name if default else ""

    if embedding_id is not KEEP:
        conversation.embedding = _embedding(user, embedding_id)
        conversation.embedding_name = conversation.embedding.name if conversation.embedding else ""
    elif conversation.embedding_name and conversation.embedding_id is None:
        raise UnknownTarget("This chat's embedding was deleted — pick another")
    if connection_id is not KEEP:
        conversation.connection = _connection(user, connection_id)
    if model is not KEEP:
        conversation.model = str(model or "").strip()[:200]
    conversation.save()

    Message.objects.create(conversation=conversation, role=Message.Role.USER, content=text)
    emb = conversation.embedding
    settings = RunSettings(
        embedding_id=conversation.embedding_id,
        connection_id=conversation.connection_id,
        model=conversation.model,
        agent_name=agent.name if agent else "Demo agent",
        embedding=(
            {"id": emb.pk, "name": emb.name, "model": emb.model, "dimensions": emb.dimensions}
            if emb
            else None
        ),
    )
    return conversation, selectors.history(conversation), settings


def _embedding(user, embedding_id) -> EmbeddingIndex | None:
    if embedding_id in (None, "", "none"):
        return None
    try:
        return rag_selectors.get_embedding(user, int(embedding_id))
    except (EmbeddingIndex.DoesNotExist, ValueError, TypeError) as exc:
        raise UnknownTarget("Unknown embedding") from exc


def _connection(user, connection_id) -> Connection | None:
    if connection_id in (None, "", "default"):
        return None
    try:
        return provider_selectors.get_connection(user, int(connection_id))
    except (Connection.DoesNotExist, ValueError, TypeError) as exc:
        raise UnknownTarget("Unknown connection") from exc


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
    conversation_id: int,
    *,
    run_id: str,
    reply: ReplyAccumulator,
    cancelled: bool,
    settings: RunSettings | None = None,
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
        # Same as the live view: a failed answer keeps no partial text (cancelled ones do).
        content="" if status == Message.Status.ERROR else reply.text,
        status=status,
        run_id=run_id,
        metadata={
            "thinking": reply.thinking,
            "tool_calls": reply.tool_calls,
            "retrieved": reply.retrieved,
            "model": reply.model,
            # What produced this answer, so it stays readable after the chat switches (0010).
            "agent": settings.agent_name if settings else "",
            "embedding": settings.embedding if settings else None,
            "error": reply.error
            or ("" if status != Message.Status.ERROR else "The run ended unexpectedly"),
        },
    )
    Conversation.objects.filter(pk=conversation_id).update(
        updated_at=message.created_at, active_run_id=""
    )
    return message
