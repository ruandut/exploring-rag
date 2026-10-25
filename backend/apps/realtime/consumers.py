"""The single websocket endpoint the frontend keeps open: /ws/events/.

Protocol (client → server):
    {"type": "auth", "token": "<JWT access token>"}   must be the first message
    {"type": "ping"}
    anything else is dispatched to a handler a domain app registered (see handlers.py),
    e.g. {"type": "agent.ask", ...} / {"type": "agent.cancel", "run_id": ...}

Server → client events are typed in frontend/src/lib/socket.ts (the event contract).
"""

import asyncio
import logging
from collections.abc import Coroutine

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .events import user_group
from .handlers import get_handler

log = logging.getLogger(__name__)

# Custom close codes (4000-4999 are reserved for applications).
CLOSE_UNAUTHENTICATED = 4401


@database_sync_to_async
def _user_from_token(raw: str):
    try:
        token = AccessToken(raw)
    except TokenError:
        return None
    User = get_user_model()
    return User.objects.filter(pk=token["user_id"], is_active=True).first()


class EventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = None
        self.group = None
        self._background: dict[str, asyncio.Task] = {}
        await self.accept()
        self.auth_deadline = asyncio.create_task(self._close_if_unauthenticated())

    async def _close_if_unauthenticated(self):
        await asyncio.sleep(settings.WS_AUTH_TIMEOUT)
        if self.user is None:
            await self.close(code=CLOSE_UNAUTHENTICATED)

    async def disconnect(self, code):
        self.auth_deadline.cancel()
        for task in self._background.values():
            task.cancel()
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")

        if self.user is None:
            await self._authenticate(kind, content)
            return

        if kind == "ping":
            await self.send_json({"type": "pong"})
            return

        handler = get_handler(kind)
        if handler is None:
            await self.send_json({"type": "error", "detail": f"Unknown message type: {kind}"})
            return
        await handler(self, content)

    async def _authenticate(self, kind, content):
        if kind != "auth":
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        user = await _user_from_token(content.get("token", ""))
        if user is None:
            await self.send_json({"type": "auth.error", "detail": "Invalid or expired token"})
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.user = user
        self.auth_deadline.cancel()
        self.group = user_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.send_json(
            {"type": "auth.ok", "user": {"id": user.id, "username": user.username}}
        )

    # --- group messages (sent via apps.realtime.events) -------------------------------
    async def user_event(self, event):
        await self.send_json(event["payload"])

    # --- background work owned by this socket (used by registered handlers) ------------
    def start_background(self, key: str, coro: Coroutine) -> None:
        task = asyncio.create_task(coro)
        self._background[key] = task
        task.add_done_callback(lambda _: self._background.pop(key, None))

    def owns_background(self, key: str) -> bool:
        return key in self._background

    def cancel_background(self, key: str) -> bool:
        task = self._background.pop(key, None)
        if task is None:
            return False
        task.cancel()
        return True
