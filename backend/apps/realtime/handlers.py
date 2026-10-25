"""Registry for client → server websocket messages.

The gateway (EventsConsumer) is platform code and must not import domain apps, so domain
apps register handlers for the message types they own, from their AppConfig.ready():

    from apps.realtime.handlers import ws_handler

    @ws_handler("agent.ask")
    async def ask(conn, message): ...

`conn` is the consumer: it exposes `user`, `send_json(...)`, and background-task helpers
(`start_background`, `cancel_background`, `owns_background`) for long-lived streams.
"""

from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[Any, dict], Awaitable[None]]

_handlers: dict[str, Handler] = {}


def ws_handler(message_type: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        if message_type in _handlers and _handlers[message_type] is not fn:
            raise RuntimeError(f"Websocket message type {message_type!r} registered twice")
        _handlers[message_type] = fn
        return fn

    return register


def get_handler(message_type: str) -> Handler | None:
    return _handlers.get(message_type)
