"""Small, non-streaming LLM calls used *inside* the RAG pipeline (query rewriting, reranking,
map/refine steps, relevance grading). The agent's own answer streams elsewhere."""

import json
import re
from typing import Protocol


class Completer(Protocol):
    """Anything with complete(prompt) — in practice a providers ChatTarget (adapter + model), so
    these steps run on whichever provider the chat or benchmark picked."""

    def complete(self, prompt: str, *, max_tokens: int = 300) -> str: ...


def parse_int_list(text: str) -> list[int] | None:
    """Pull the first JSON array of integers out of a model reply, if there is one."""
    match = re.search(r"\[[\d,\s]*\]", text)
    if not match:
        return None
    try:
        values = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return [v for v in values if isinstance(v, int)]
