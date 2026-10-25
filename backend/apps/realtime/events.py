"""Push events to a user's open websockets from anywhere (API views, Hatchet workers).

Every browser tab a user has open joins the Channels group `user.<id>`. Sending to that
group goes through Redis, so it works from any process — that's how a Hatchet worker
reaches the Daphne process that holds the socket.

Event payloads are plain dicts with a `type` field; the frontend switches on it.
See CLAUDE.md "Websocket event contract" before adding a new type.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def user_group(user_id: int) -> str:
    return f"user.{user_id}"


async def asend_to_user(user_id: int, payload: dict) -> None:
    await get_channel_layer().group_send(
        user_group(user_id), {"type": "user.event", "payload": payload}
    )


def send_to_user(user_id: int, payload: dict) -> None:
    async_to_sync(asend_to_user)(user_id, payload)
