"""agent.ask / agent.cancel over the websocket. Registered from ChatConfig.ready().

chat is the top layer: it stores the conversation, asks `agents` to start a run, relays the
run's Hatchet stream to the socket, and saves the reply when the stream ends — including a
partial reply when the user presses Stop.
"""

import asyncio

from channels.db import database_sync_to_async

from apps.agents import services as agent_services
from apps.jobs.ws_handlers import relay_run_stream
from apps.realtime.handlers import ws_handler

from . import services


@ws_handler("agent.ask")
async def agent_ask(conn, message: dict) -> None:
    text = str(message.get("message", "")).strip()[:8000]
    agent_key = str(message.get("agent_id", agent_services.DEMO_AGENT))
    if not text:
        await conn.send_json({"type": "error", "detail": "Empty message"})
        return
    try:
        conversation, history = await database_sync_to_async(services.begin_turn)(
            conn.user,
            agent_key=agent_key,
            conversation_id=message.get("conversation_id"),
            text=text,
        )
    except services.UnknownTarget as exc:
        await conn.send_json({"type": "error", "detail": str(exc)})
        return

    run_id = await agent_services.astart_run(conn.user, agent_key, history)
    if not await database_sync_to_async(services.mark_run_started)(conversation.pk, run_id):
        # Deleted while the run was starting: nobody can read this answer, so stop it now.
        await database_sync_to_async(services.cancel_run)(run_id)
        await conn.send_json({"type": "agent.cancelled", "run_id": run_id})
        return
    await conn.send_json(
        {"type": "agent.started", "run_id": run_id, "conversation_id": conversation.pk}
    )
    conn.start_background(run_id, _relay_and_save(conn, run_id, conversation.pk))


async def _relay_and_save(conn, run_id: str, conversation_id: int) -> None:
    reply = services.ReplyAccumulator()
    cancelled = False
    try:
        await relay_run_stream(
            conn, run_id, fallback_type="agent.token", error_type="agent.error", on_event=reply.add
        )
    except asyncio.CancelledError:
        cancelled = True  # Stop pressed, or the socket closed
        raise
    finally:
        await database_sync_to_async(services.save_reply)(
            conversation_id, run_id=run_id, reply=reply, cancelled=cancelled
        )


@ws_handler("agent.cancel")
async def agent_cancel(conn, message: dict) -> None:
    run_id = str(message.get("run_id", ""))
    # Only runs started on this socket can be cancelled from it.
    if not conn.owns_background(run_id):
        await conn.send_json({"type": "error", "detail": "Unknown run"})
        return
    from apps.jobs.hatchet import get_hatchet

    await get_hatchet().runs.aio_cancel(run_id)
    conn.cancel_background(run_id)
    await conn.send_json({"type": "agent.cancelled", "run_id": run_id})
