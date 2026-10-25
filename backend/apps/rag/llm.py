"""Small, non-streaming LLM calls used *inside* the RAG pipeline (query rewriting, reranking,
map/refine steps, relevance grading). The agent's own answer streams elsewhere."""

import json
import re

from openai import OpenAI


def complete(client: OpenAI, model: str, prompt: str, *, max_tokens: int = 300) -> str:
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0,
    )
    return (res.choices[0].message.content or "").strip()


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
