"""Provider adapters (spec 0008). The only package that imports a provider SDK — the
architecture guard (apps/core/test_architecture.py) fails if any other module does."""

from .base import (
    EFFORTS,
    Adapter,
    Cancelled,
    Done,
    EmbeddingsUnsupported,
    Event,
    ProviderError,
    Text,
    Thinking,
    Tool,
    ToolCall,
    ToolsUnsupported,
)

KINDS = {
    "openai": "OpenAI-compatible",
    "anthropic": "Anthropic",
    "google": "Google",
}


def make_adapter(kind: str, base_url: str, api_key: str, *, timeout: float) -> Adapter:
    # Imported lazily so a missing optional SDK only breaks the provider that needs it.
    if kind == "anthropic":
        from .anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(base_url, api_key, timeout=timeout)
    if kind == "google":
        from .google_adapter import GoogleAdapter

        return GoogleAdapter(base_url, api_key, timeout=timeout)
    from .openai_compat import OpenAICompatible

    return OpenAICompatible(base_url, api_key, timeout=timeout)


__all__ = [
    "EFFORTS",
    "KINDS",
    "Adapter",
    "Cancelled",
    "Done",
    "EmbeddingsUnsupported",
    "Event",
    "ProviderError",
    "Text",
    "Thinking",
    "Tool",
    "ToolCall",
    "ToolsUnsupported",
    "make_adapter",
]
