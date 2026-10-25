"""Acceptance tests for specs/0001-foundation.md (websocket)."""

import pytest
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import AccessToken

from apps.realtime.consumers import CLOSE_UNAUTHENTICATED, EventsConsumer
from apps.realtime.events import asend_to_user

pytestmark = pytest.mark.django_db(transaction=True)


def connect():
    return WebsocketCommunicator(EventsConsumer.as_asgi(), "/ws/events/")


async def test_at_0001_04_valid_token_authenticates_socket(user):
    ws = connect()
    assert (await ws.connect())[0]
    await ws.send_json_to({"type": "auth", "token": str(AccessToken.for_user(user))})
    assert (await ws.receive_json_from())["type"] == "auth.ok"
    await ws.disconnect()


async def test_at_0001_04_invalid_token_closes_socket(user):
    ws = connect()
    await ws.connect()
    await ws.send_json_to({"type": "auth", "token": "garbage"})
    assert (await ws.receive_json_from())["type"] == "auth.error"
    assert (await ws.receive_output())["code"] == CLOSE_UNAUTHENTICATED


async def test_at_0001_04_first_message_must_be_auth(user):
    ws = connect()
    await ws.connect()
    await ws.send_json_to({"type": "ping"})
    assert (await ws.receive_output())["code"] == CLOSE_UNAUTHENTICATED


async def test_at_0001_05_events_sent_to_user_reach_their_socket(user):
    ws = connect()
    await ws.connect()
    await ws.send_json_to({"type": "auth", "token": str(AccessToken.for_user(user))})
    await ws.receive_json_from()  # auth.ok

    await asend_to_user(user.id, {"type": "job.progress", "step": 1, "total": 2})
    assert await ws.receive_json_from() == {"type": "job.progress", "step": 1, "total": 2}

    await asend_to_user(user.id + 1, {"type": "job.progress", "step": 9, "total": 9})
    assert await ws.receive_nothing()  # other users' events never arrive
    await ws.disconnect()


async def test_messages_are_dispatched_to_registered_handlers(user):
    from apps.realtime.handlers import _handlers, ws_handler

    @ws_handler("test.echo")
    async def echo(conn, message):
        await conn.send_json({"type": "test.echoed", "by": conn.user.username})

    try:
        ws = connect()
        await ws.connect()
        await ws.send_json_to({"type": "auth", "token": str(AccessToken.for_user(user))})
        await ws.receive_json_from()  # auth.ok
        await ws.send_json_to({"type": "test.echo"})
        assert await ws.receive_json_from() == {"type": "test.echoed", "by": "alice"}
        await ws.send_json_to({"type": "nope"})
        assert (await ws.receive_json_from())["type"] == "error"
        await ws.disconnect()
    finally:
        _handlers.pop("test.echo", None)


async def test_at_0009_05_a_pushed_event_can_cancel_a_sockets_background_task(user):
    """REST code (deleting a chat) stops a relay that a socket started, via the user group."""
    import asyncio

    from apps.realtime.handlers import _handlers, ws_handler

    cancelled = asyncio.Event()

    async def forever():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    @ws_handler("test.start")
    async def start(conn, message):
        conn.start_background("run-1", forever())
        await conn.send_json({"type": "test.started"})

    try:
        ws = connect()
        await ws.connect()
        await ws.send_json_to({"type": "auth", "token": str(AccessToken.for_user(user))})
        await ws.receive_json_from()  # auth.ok
        await ws.send_json_to({"type": "test.start"})
        await ws.receive_json_from()  # test.started
        payload = {"type": "agent.cancelled", "run_id": "run-1"}
        await asend_to_user(user.id, payload, cancel_background="run-1")
        assert await ws.receive_json_from() == payload
        await asyncio.wait_for(cancelled.wait(), 1)
        await ws.disconnect()
    finally:
        _handlers.pop("test.start", None)
