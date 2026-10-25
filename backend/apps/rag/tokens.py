"""Approximate token counting.

Real tokenizers (tiktoken etc.) are model-specific and some download vocabularies at runtime.
For *sizing chunks* an approximation is enough: words and punctuation marks each count as one
token, which lands within ~25% of BPE tokenizers for English prose. Never use this for billing.
"""

import re

_TOKEN = re.compile(r"\w+|[^\w\s]")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text)


def count_tokens(text: str) -> int:
    return len(_TOKEN.findall(text))
