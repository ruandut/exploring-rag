"""Shared helper for relaying a Hatchet run's stream to a websocket.

Message handlers themselves live in the app that owns them (agent.ask / agent.cancel are in
apps/chat/ws_handlers.py) — this platform module only provides the plumbing.
"""

import asyncio
import json
import logging
from collections.abc import Callable

log = logging.getLogger(__name__)


async def relay_run_stream(
    conn,
    run_id: str,
    *,
    fallback_type: str,
    error_type: str,
    on_event: Callable[[dict], None] | None = None,
) -> None:
    """Forward every chunk a Hatchet task publishes with ctx.put_stream() to the socket.

    Chunks are JSON events; anything that isn't JSON is sent as `fallback_type` text.
    `on_event` sees each event too (e.g. to save the final answer).
    """
    from .hatchet import get_hatchet

    try:
        async for chunk in get_hatchet().runs.subscribe_to_stream(run_id):
            try:
                event = json.loads(chunk)
            except json.JSONDecodeError:
                event = {"type": fallback_type, "text": chunk}
            if on_event:
                on_event(event)
            await conn.send_json({**event, "run_id": run_id})
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - report stream failures to the UI
        log.exception("Stream failed for run %s", run_id)
        event = {"type": error_type, "detail": str(exc)}
        if on_event:
            on_event(event)
        await conn.send_json({**event, "run_id": run_id})
