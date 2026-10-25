"""Write-side logic for providers, plus the LLM client factory every other app uses."""

import time
from dataclasses import asdict, dataclass

from django.db import transaction
from openai import OpenAI, OpenAIError

from .crypto import encrypt
from .models import Connection, ProviderConfig
from .selectors import get_api_key, get_provider_config

# Local reasoning models (e.g. Gemma on Ollama) can think for a minute or more before the first
# token, and judges ask for long JSON verdicts, so 30 seconds was too short. Quick calls (Test
# connection, model lists) pass their own shorter timeout.
LLM_TIMEOUT_SECONDS = 300.0


def build_client(base_url: str, api_key: str, *, timeout: float = LLM_TIMEOUT_SECONDS) -> OpenAI:
    # Local servers like Ollama ignore the key, but the SDK requires a non-empty one.
    return OpenAI(
        base_url=base_url, api_key=api_key or "not-needed", timeout=timeout, max_retries=0
    )


def client_for(user) -> OpenAI:
    """The OpenAI-compatible client for a user's saved provider. Used by rag / agents / evals."""
    config = get_provider_config(user)
    if config is None:
        raise ValueError("No LLM provider configured")
    return build_client(config.base_url, get_api_key(config))


def embedding_client(user, connection: Connection | None) -> OpenAI:
    """The client an embedding embeds with: its connection, or the default provider."""
    if connection is not None:
        return build_client(connection.base_url, get_api_key(connection))
    return client_for(user)


@dataclass
class ChatTarget:
    """Where an agent sends chat requests: a client plus the model name to ask for."""

    client: OpenAI
    model: str
    label: str  # shown in the UI, e.g. "Ollama (local) · gemma4:e4b"


def chat_target(user, *, connection: Connection | None, model: str) -> ChatTarget:
    """An agent's connection + model, falling back to the default provider and its chat model."""
    if connection is not None:
        if not model:
            raise ValueError(f"Pick a model for the connection “{connection.name}”")
        key = get_api_key(connection)
        return ChatTarget(
            build_client(connection.base_url, key), model, f"{connection.name} · {model}"
        )
    config = get_provider_config(user)
    if config is None:
        raise ValueError("No LLM provider configured — add one in Settings.")
    model = model or config.chat_model
    return ChatTarget(client_for(user), model, f"Default provider · {model}")


def save_connection(user, *, data: dict, instance: Connection | None = None) -> Connection:
    conn = instance or Connection(owner=user)
    for field in ("name", "base_url"):
        if field in data:
            setattr(conn, field, data[field])
    if "api_key" in data:
        key = data["api_key"]
        conn.api_key_encrypted = encrypt(key) if key else ""
        conn.api_key_last4 = key[-4:] if key else ""
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
    for field in ("base_url", "chat_model"):
        if field in data:
            setattr(config, field, data[field])
    if "api_key" in data:
        key = data["api_key"]
        config.api_key_encrypted = encrypt(key) if key else ""
        config.api_key_last4 = key[-4:] if key else ""
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
    # Surface the provider's own message (e.g. "Incorrect API key provided") when there is one.
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return str(exc) or exc.__class__.__name__


def test_connection(*, base_url: str, api_key: str, chat_model: str) -> dict:
    """Make one tiny chat completion against the endpoint. (Embeddings have their own Test.)"""
    client = build_client(base_url, api_key, timeout=20.0)

    start = time.monotonic()
    try:
        reply = client.chat.completions.create(
            model=chat_model,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=5,
        )
        text = (reply.choices[0].message.content or "").strip()
        chat = Check(True, f"Replied “{text[:40]}”", int((time.monotonic() - start) * 1000))
    except OpenAIError as exc:
        chat = Check(False, error_message(exc))

    return asdict(ConnectionReport(chat.ok, chat))


def test_embedding(*, client: OpenAI, model: str) -> dict:
    """One embedding call: does the model answer, and how long are its vectors?"""
    start = time.monotonic()
    try:
        emb = client.embeddings.create(model=model, input="ping")
    except OpenAIError as exc:
        return {"ok": False, "detail": error_message(exc), "latency_ms": None, "dimensions": None}
    dims = len(emb.data[0].embedding)
    latency = int((time.monotonic() - start) * 1000)
    return {"ok": True, "detail": f"{dims} dimensions", "latency_ms": latency, "dimensions": dims}
