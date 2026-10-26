"""Write-side logic for providers, plus the adapter factory every other app uses.

Other apps never touch a provider SDK: they ask for an adapter (`adapter_for`) or a chat
target (`chat_target`) and use the neutral interface in `llm/base.py`.
"""

import time
from dataclasses import asdict, dataclass

from django.db import transaction

from .crypto import encrypt
from .llm import Adapter, ProviderError, make_adapter
from .models import Connection, ProviderConfig
from .selectors import get_api_key, get_provider_config

# Local reasoning models (e.g. Gemma on Ollama) can think for a minute or more before the first
# token, and judges ask for long JSON verdicts, so 30 seconds was too short. Quick calls (Test
# connection, model lists) pass their own shorter timeout.
LLM_TIMEOUT_SECONDS = 300.0


def build_adapter(
    kind: str, base_url: str, api_key: str, *, timeout: float = LLM_TIMEOUT_SECONDS
) -> Adapter:
    return make_adapter(kind, base_url, api_key, timeout=timeout)


def adapter_for(
    user, connection: Connection | None, *, timeout: float = LLM_TIMEOUT_SECONDS
) -> Adapter:
    """The adapter for a connection, or for the user's default provider when it's None."""
    if connection is not None:
        return build_adapter(
            connection.kind, connection.base_url, get_api_key(connection), timeout=timeout
        )
    config = get_provider_config(user)
    if config is None:
        raise ValueError("No LLM provider configured")
    return build_adapter(config.kind, config.base_url, get_api_key(config), timeout=timeout)


@dataclass
class ChatTarget:
    """Where chat requests go: an adapter plus the model name to ask for."""

    adapter: Adapter
    model: str
    label: str  # shown in the UI, e.g. "Ollama (local) · gemma4:e4b"

    def complete(self, prompt: str, *, max_tokens: int = 300) -> str:
        return self.adapter.complete(self.model, prompt, max_tokens=max_tokens)


def chat_target(user, *, connection: Connection | None, model: str) -> ChatTarget:
    """A connection + model, falling back to the default provider and its chat model."""
    if connection is not None:
        if not model:
            raise ValueError(f"Pick a model for the connection “{connection.name}”")
        return ChatTarget(adapter_for(user, connection), model, f"{connection.name} · {model}")
    config = get_provider_config(user)
    if config is None:
        raise ValueError("No LLM provider configured — add one in Settings.")
    model = model or config.chat_model
    return ChatTarget(adapter_for(user, None), model, f"Default provider · {model}")


def _set_key(obj, data: dict) -> None:
    if "api_key" in data:
        key = data["api_key"]
        obj.api_key_encrypted = encrypt(key) if key else ""
        obj.api_key_last4 = key[-4:] if key else ""


def save_connection(user, *, data: dict, instance: Connection | None = None) -> Connection:
    conn = instance or Connection(owner=user)
    for field in ("name", "kind", "base_url"):
        if field in data:
            setattr(conn, field, data[field])
    _set_key(conn, data)
    conn.save()
    return conn


@transaction.atomic
def save_provider_config(user, *, data: dict) -> ProviderConfig:
    """Create or update the user's provider.

    `data` may omit `api_key` to keep the stored one; an empty string clears it. Embeddings
    using the default provider pick up a new URL or key on their next indexing run; their
    model is their own, so nothing is re-indexed here.
    """
    config = get_provider_config(user) or ProviderConfig(owner=user)
    for field in ("kind", "base_url", "chat_model"):
        if field in data:
            setattr(config, field, data[field])
    _set_key(config, data)
    config.save()
    return config


@dataclass
class Check:
    ok: bool
    detail: str
    latency_ms: int | None = None


@dataclass
class ConnectionReport:
    ok: bool
    chat: Check


def error_message(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


def test_connection(*, kind: str, base_url: str, api_key: str, chat_model: str) -> dict:
    """One tiny completion against the endpoint, whatever its kind. (Embeddings have their own
    Test.)"""
    adapter = build_adapter(kind, base_url, api_key, timeout=60.0)
    start = time.monotonic()
    try:
        text = adapter.complete(chat_model, "Reply with the single word: OK", max_tokens=5)
        chat = Check(True, f"Replied “{text[:40]}”", int((time.monotonic() - start) * 1000))
    except ProviderError as exc:
        chat = Check(False, error_message(exc))
    return asdict(ConnectionReport(chat.ok, chat))


def test_embedding(*, adapter: Adapter, model: str) -> dict:
    """One embedding call: does the model answer, and how long are its vectors?"""
    start = time.monotonic()
    try:
        [vector] = adapter.embed(model, ["ping"])
    except ProviderError as exc:
        return {"ok": False, "detail": error_message(exc), "latency_ms": None, "dimensions": None}
    dims = len(vector)
    latency = int((time.monotonic() - start) * 1000)
    return {"ok": True, "detail": f"{dims} dimensions", "latency_ms": latency, "dimensions": dims}
