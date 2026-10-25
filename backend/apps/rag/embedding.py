"""Step 4 of indexing: turn chunk texts into vectors with the user's provider."""

from collections.abc import Callable

from openai import OpenAI

BATCH_SIZE = 64  # inputs per embeddings request; keeps requests well under provider limits


def make_embedder(client: OpenAI, model: str) -> Callable[[list[str]], list[list[float]]]:
    def embed(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            res = client.embeddings.create(model=model, input=batch)
            # Providers may return items out of order; `index` is authoritative.
            vectors.extend(item.embedding for item in sorted(res.data, key=lambda d: d.index))
        return vectors

    return embed
