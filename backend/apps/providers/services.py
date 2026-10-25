"""Write-side logic for providers, plus the LLM client factory every other app uses."""

import time
from dataclasses import asdict, dataclass

from django.db import transaction
from openai import OpenAI, OpenAIError

from apps.jobs.events import push_event_on_commit

from .crypto import encrypt
from .models import Connection, ProviderConfig
from .selectors import get_api_key, get_provider_config

# Fields whose change invalidates every stored embedding.
EMBEDDING_FIELDS = ("base_url", "embedding_model", "embedding_dimensions")


class ReindexConfirmationRequired(Exception):
    """Saving would change embeddings; the caller must confirm a full re-index."""


def build_client(base_url: str, api_key: str, *, timeout: float = 30.0) -> OpenAI:
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


def list_models(base_url: str, api_key: str) -> list[str]:
    """Model ids the endpoint offers (GET /models). Ollama lists every pulled model here."""
    client = build_client(base_url, api_key, timeout=10.0)
    return sorted(m.id for m in client.models.list())


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
def save_provider_config(user, *, data: dict, confirm_reindex: bool) -> tuple[ProviderConfig, bool]:
    """Create or update the user's provider. Returns (config, reindex_started).

    `data` may omit `api_key` to keep the stored one; an empty string clears it.
    """
    config = get_provider_config(user)
    embeddings_change = config is not None and any(
        k in data and data[k] != getattr(config, k) for k in EMBEDDING_FIELDS
    )
    if embeddings_change and not confirm_reindex:
        raise ReindexConfirmationRequired

    config = config or ProviderConfig(owner=user)
    for field in ("base_url", "chat_model", "embedding_model", "embedding_dimensions"):
        if field in data:
            setattr(config, field, data[field])
    if "api_key" in data:
        key = data["api_key"]
        config.api_key_encrypted = encrypt(key) if key else ""
        config.api_key_last4 = key[-4:] if key else ""
    config.save()

    if embeddings_change:
        # providers sits below rag, so it announces the change instead of calling rag.
        push_event_on_commit("provider.embedding_changed", {"user_id": user.id})
    return config, embeddings_change


@dataclass
class Check:
    ok: bool
    detail: str
    latency_ms: int | None = None


@dataclass
class ConnectionReport:
    ok: bool
    chat: Check
    embeddings: Check
    embedding_dimensions: int | None


def error_message(exc: Exception) -> str:
    # Surface the provider's own message (e.g. "Incorrect API key provided") when there is one.
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return str(exc) or exc.__class__.__name__


def test_connection(*, base_url: str, api_key: str, chat_model: str, embedding_model: str) -> dict:
    """Make one tiny chat completion and one embedding call against the endpoint."""
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

    dims = None
    start = time.monotonic()
    try:
        emb = client.embeddings.create(model=embedding_model, input="ping")
        dims = len(emb.data[0].embedding)
        embeddings = Check(True, f"{dims} dimensions", int((time.monotonic() - start) * 1000))
    except OpenAIError as exc:
        embeddings = Check(False, error_message(exc))

    report = ConnectionReport(chat.ok and embeddings.ok, chat, embeddings, dims)
    return asdict(report)
