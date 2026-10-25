"""What kind of model is each model an endpoint offers? (spec 0010, the model picker)

OpenAI's `GET /models` only lists ids — it doesn't say which ones embed and which ones chat.
So the picker asks, in order:

1. **The endpoint itself**, when it says more:
   - Ollama (detected by `GET <root>/api/version`): `POST /api/show` per model lists its
     capabilities ("completion", "tools", "embedding") and `<arch>.embedding_length`.
   - OpenRouter: each model's `architecture.output_modalities`.
2. **A built-in table** of well-known models (kind + dimensions).
3. **The name** ("embed", "bge", "e5-", "gte-", "minilm") — labelled "guessed from the name".
4. Otherwise **unknown** — always listed, because a wrong guess must never hide a model.
"""

import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

from .services import build_client

SHOW_CONCURRENCY = 8  # /api/show calls at once
SHOW_TIMEOUT = 5.0  # seconds per Ollama call

# id → (kind, dimensions). Prefix-free ids; Ollama tags (":latest", ":v1.5") are stripped.
KNOWN: dict[str, tuple[str, int | None]] = {
    "text-embedding-3-small": ("embedding", 1536),
    "text-embedding-3-large": ("embedding", 3072),
    "text-embedding-ada-002": ("embedding", 1536),
    "nomic-embed-text": ("embedding", 768),
    "mxbai-embed-large": ("embedding", 1024),
    "bge-m3": ("embedding", 1024),
    "all-minilm": ("embedding", 384),
    "snowflake-arctic-embed": ("embedding", 1024),
    "gpt-5": ("chat", None),
    "gpt-5-mini": ("chat", None),
    "gpt-4o": ("chat", None),
    "gpt-4o-mini": ("chat", None),
}
EMBEDDING_NAME = re.compile(r"embed|bge|(^|[/_-])e5-|(^|[/_-])gte-|minilm", re.IGNORECASE)

HINTS = {
    "ollama": "Run `ollama pull nomic-embed-text`, then press Refresh.",
    "openai": "Try text-embedding-3-small.",
    "openrouter": "OpenRouter has no embedding models — use another connection.",
}


@dataclass
class ModelInfo:
    id: str
    kind: str  # chat | embedding | unknown
    source: str  # endpoint | known | guessed | unknown
    dimensions: int | None = None
    tools: bool | None = None  # can it call tools? None = not known


class EndpointError(Exception):
    pass


def _json(url: str, body: dict | None = None) -> dict:
    """GET (or POST `body`) JSON. Ollama's own API isn't OpenAI-shaped, so the SDK can't call
    it; the standard library is enough for these two small calls."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=SHOW_TIMEOUT) as res:  # noqa: S310
            return json.loads(res.read() or b"{}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise EndpointError(str(exc)) from exc


def _root(base_url: str) -> str:
    """http://localhost:11434/v1 → http://localhost:11434 (where Ollama's own API lives)."""
    url = base_url.rstrip("/")
    return url[: -len("/v1")] if url.endswith("/v1") else url


def endpoint_type(base_url: str, api_key: str) -> str:
    host = urlparse(base_url).hostname or ""
    if host.endswith("openrouter.ai"):
        return "openrouter"
    if host.endswith("openai.com"):
        return "openai"
    try:
        if "version" in _json(f"{_root(base_url)}/api/version"):
            return "ollama"
    except EndpointError:
        pass
    return "openai-compatible"


def _from_table_or_name(model_id: str) -> ModelInfo:
    bare = model_id.split("/")[-1].split(":")[0]
    if bare in KNOWN:
        kind, dims = KNOWN[bare]
        return ModelInfo(model_id, kind, "known", dims)
    if EMBEDDING_NAME.search(bare):
        return ModelInfo(model_id, "embedding", "guessed")
    return ModelInfo(model_id, "unknown", "unknown")


def _ollama_show(root: str, model_id: str) -> ModelInfo:
    try:
        body = _json(f"{root}/api/show", {"model": model_id})
    except EndpointError:
        return _from_table_or_name(model_id)
    capabilities = set(body.get("capabilities") or [])
    info = body.get("model_info") or {}
    dims = next((v for k, v in info.items() if k.endswith(".embedding_length")), None)
    if "embedding" in capabilities:
        return ModelInfo(model_id, "embedding", "endpoint", dims)
    if "completion" in capabilities:
        return ModelInfo(model_id, "chat", "endpoint", None, "tools" in capabilities)
    return _from_table_or_name(model_id)


def list_models(base_url: str, api_key: str) -> tuple[str, list[ModelInfo]]:
    """(endpoint type, every model with its kind). Raises OpenAIError if unreachable."""
    kind = endpoint_type(base_url, api_key)
    client = build_client(base_url, api_key, timeout=10.0)
    listed = list(client.models.list())
    ids = sorted(m.id for m in listed)

    if kind == "ollama":
        root = _root(base_url)
        with ThreadPoolExecutor(max_workers=SHOW_CONCURRENCY) as pool:
            return kind, list(pool.map(lambda m: _ollama_show(root, m), ids))

    if kind == "openrouter":
        out = []
        for m in sorted(listed, key=lambda m: m.id):
            arch = (m.model_extra or {}).get("architecture") or {}
            outputs = set(arch.get("output_modalities") or [])
            if "embeddings" in outputs:
                out.append(ModelInfo(m.id, "embedding", "endpoint"))
            elif outputs:
                out.append(ModelInfo(m.id, "chat", "endpoint"))
            else:
                out.append(_from_table_or_name(m.id))
        return kind, out

    return kind, [_from_table_or_name(m) for m in ids]


def catalogue(base_url: str, api_key: str, *, want: str | None) -> dict:
    """The picker's payload. want = "embedding" | "chat" keeps that kind plus unknowns (which
    are always listed); None lists everything."""
    endpoint, models = list_models(base_url, api_key)
    if want in ("embedding", "chat"):
        models = [m for m in models if m.kind in (want, "unknown")]
    has_wanted = any(m.kind == want for m in models)
    hint = HINTS.get(endpoint, "") if want == "embedding" and not has_wanted else ""
    return {"endpoint": endpoint, "hint": hint, "models": [asdict(m) for m in models]}
