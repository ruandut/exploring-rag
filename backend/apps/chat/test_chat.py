import pytest
from channels.testing import WebsocketCommunicator
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.agents.models import Agent
from apps.chat import services
from apps.chat.models import Conversation, Message
from apps.realtime.consumers import EventsConsumer


@pytest.fixture
def agent(user):
    return Agent.objects.create(owner=user, name="Helper")


def test_begin_turn_starts_a_conversation_and_returns_history(db, user, agent):
    convo, history = services.begin_turn(
        user, agent_key=str(agent.pk), conversation_id=None, text="Hi there"
    )
    assert convo.title == "Hi there" and convo.agent == agent
    assert history == [{"role": "user", "content": "Hi there"}]
    services.save_reply(
        convo.pk,
        run_id="r1",
        reply=services.ReplyAccumulator(text="Hello!", finished=True),
        cancelled=False,
    )
    _, history = services.begin_turn(
        user, agent_key=str(agent.pk), conversation_id=convo.pk, text="And again"
    )
    assert [m["content"] for m in history] == ["Hi there", "Hello!", "And again"]


def test_other_users_agents_and_conversations_are_rejected(db, user, other_user, agent):
    with pytest.raises(services.UnknownTarget):
        services.begin_turn(other_user, agent_key=str(agent.pk), conversation_id=None, text="x")
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="x")
    with pytest.raises(services.UnknownTarget):
        services.begin_turn(other_user, agent_key="demo", conversation_id=convo.pk, text="x")


@pytest.mark.parametrize(
    ("reply", "cancelled", "status"),
    [
        (services.ReplyAccumulator(text="ok", finished=True), False, "done"),
        (services.ReplyAccumulator(text="part"), True, "cancelled"),
        (services.ReplyAccumulator(error="boom"), False, "error"),
        (services.ReplyAccumulator(text="cut off"), False, "error"),
    ],
)
def test_reply_status(db, user, reply, cancelled, status):
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="x")
    msg = services.save_reply(convo.pk, run_id="r", reply=reply, cancelled=cancelled)
    assert msg.status == status


def test_conversations_api_is_private(db, user, other_user, auth_api):
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="Hello")
    assert [c["title"] for c in auth_api.get("/api/chat/conversations/").json()] == ["Hello"]
    detail = auth_api.get(f"/api/chat/conversations/{convo.pk}/").json()
    assert [m["role"] for m in detail["messages"]] == ["user"]
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(f"/api/chat/conversations/{convo.pk}/").status_code == 404


@pytest.mark.django_db(transaction=True)
async def test_ask_streams_and_saves_the_reply(user, agent, monkeypatch):
    async def fake_start(user, agent_key, messages):
        return "run-1"

    async def fake_relay(conn, run_id, *, fallback_type, error_type, on_event):
        for event in [
            {"type": "agent.token", "text": "Hello"},
            {"type": "agent.done", "model": "Default provider · m"},
        ]:
            on_event(event)
            await conn.send_json({**event, "run_id": run_id})

    monkeypatch.setattr("apps.chat.ws_handlers.agent_services.astart_run", fake_start)
    monkeypatch.setattr("apps.chat.ws_handlers.relay_run_stream", fake_relay)

    ws = WebsocketCommunicator(EventsConsumer.as_asgi(), "/ws/events/")
    await ws.connect()
    await ws.send_json_to({"type": "auth", "token": str(AccessToken.for_user(user))})
    await ws.receive_json_from()
    await ws.send_json_to({"type": "agent.ask", "agent_id": str(agent.pk), "message": "Hi"})
    started = await ws.receive_json_from()
    assert started["type"] == "agent.started" and started["run_id"] == "run-1"
    assert (await ws.receive_json_from())["text"] == "Hello"
    assert (await ws.receive_json_from())["type"] == "agent.done"
    await ws.disconnect()

    from channels.db import database_sync_to_async

    @database_sync_to_async
    def saved():
        convo = Conversation.objects.get(pk=started["conversation_id"])
        return [(m.role, m.content, m.status) for m in convo.messages.all()]

    assert await saved() == [("user", "Hi", "done"), ("assistant", "Hello", "done")]
    assert Message  # imported for readability of the model under test


# --- spec 0009: delete a chat ---------------------------------------------------------------


@pytest.fixture
def cancelled(monkeypatch):
    """Records Hatchet cancels and socket pushes instead of reaching Hatchet / Redis."""
    calls: dict[str, list] = {"runs": [], "pushes": []}
    monkeypatch.setattr(services, "cancel_run", calls["runs"].append)
    monkeypatch.setattr(
        services,
        "send_to_user",
        lambda user_id, payload, cancel_background=None: calls["pushes"].append(
            (user_id, payload, cancel_background)
        ),
    )
    return calls


def test_at_0009_02_delete_removes_the_conversation_and_its_messages(db, user, auth_api, cancelled):
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="Hello")
    services.save_reply(
        convo.pk,
        run_id="r1",
        reply=services.ReplyAccumulator(text="Hi", finished=True),
        cancelled=False,
    )
    assert auth_api.delete(f"/api/chat/conversations/{convo.pk}/").status_code == 204
    assert not Conversation.objects.filter(pk=convo.pk).exists()
    assert not Message.objects.filter(conversation_id=convo.pk).exists()
    assert auth_api.get(f"/api/chat/conversations/{convo.pk}/").status_code == 404
    assert cancelled["runs"] == []  # nothing was streaming


def test_at_0009_03_cannot_delete_another_users_conversation(db, user, other_user, cancelled):
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="Mine")
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.delete(f"/api/chat/conversations/{convo.pk}/").status_code == 404
    assert bob.delete("/api/chat/conversations/not-a-number/").status_code == 404
    assert Conversation.objects.filter(pk=convo.pk).exists()
    with pytest.raises(Conversation.DoesNotExist):
        services.delete_conversation(other_user, convo.pk)


def test_at_0009_05_deleting_a_streaming_conversation_cancels_the_run(db, user, cancelled):
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="Long")
    assert services.mark_run_started(convo.pk, "run-9")
    services.delete_conversation(user, convo.pk)
    assert cancelled["runs"] == ["run-9"]
    assert cancelled["pushes"] == [
        (user.pk, {"type": "agent.cancelled", "run_id": "run-9"}, "run-9")
    ]
    # The relay's finally-block still tries to save the partial reply: nothing is stored.
    reply = services.ReplyAccumulator(text="part")
    assert services.save_reply(convo.pk, run_id="run-9", reply=reply, cancelled=True) is None
    assert not Message.objects.filter(conversation_id=convo.pk).exists()
    # A run that only finished starting after the delete is reported as orphaned.
    assert services.mark_run_started(convo.pk, "run-10") is False


def test_save_reply_clears_the_active_run(db, user):
    convo, _ = services.begin_turn(user, agent_key="demo", conversation_id=None, text="x")
    services.mark_run_started(convo.pk, "run-1")
    services.save_reply(
        convo.pk,
        run_id="run-1",
        reply=services.ReplyAccumulator(text="ok", finished=True),
        cancelled=False,
    )
    convo.refresh_from_db()
    assert convo.active_run_id == ""
