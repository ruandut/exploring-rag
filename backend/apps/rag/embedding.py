"""Step 4 of indexing: turn chunk texts into vectors, with whichever provider the embedding uses.

Batching lives here, once, for every provider; the adapter embeds one batch."""

from collections.abc import Callable

from apps.providers.llm import Adapter

BATCH_SIZE = 64  # inputs per embeddings request; keeps requests well under provider limits


def make_embedder(adapter: Adapter, model: str) -> Callable[[list[str]], list[list[float]]]:
    def embed(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(adapter.embed(model, texts[start : start + BATCH_SIZE]))
        return vectors

    return embed
