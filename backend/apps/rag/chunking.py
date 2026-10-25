"""Step 3 of indexing: split text into chunks. Pure functions — no DB, no network
(semantic chunking takes an `embed` callable so it can be tested with a fake).

Every strategy returns ChunkDrafts whose `text` is at most `size` tokens (approximate, see
tokens.py), with `overlap` tokens repeated between neighbours.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from .tokens import count_tokens, tokenize

Embed = Callable[[list[str]], list[list[float]]]


@dataclass
class ChunkDraft:
    text: str
    token_count: int
    heading: str = ""  # nearest Markdown heading path, e.g. "Setup › Install"
    parent_text: str = ""  # parent_document strategy: the bigger context given to the LLM


# --- fixed --------------------------------------------------------------------------------


def fixed(text: str, size: int, overlap: int) -> list[ChunkDraft]:
    """Every `size` tokens, stepping by size - overlap. Ignores sentence boundaries."""
    spans = [m.span() for m in re.finditer(r"\w+|[^\w\s]", text)]
    step = size - overlap
    out = []
    for start in range(0, len(spans), step):
        window = spans[start : start + size]
        out.append(_draft(text[window[0][0] : window[-1][1]]))
        if start + size >= len(spans):
            break
    return out


# --- recursive ----------------------------------------------------------------------------

SEPARATORS = ["\n\n", "\n", ". ", " "]


def recursive(text: str, size: int, overlap: int) -> list[ChunkDraft]:
    """Split on the coarsest separator that works (paragraphs → lines → sentences → words),
    then greedily pack pieces up to `size`, carrying `overlap` tokens into the next chunk."""
    pieces = _split(text, size, SEPARATORS)
    return [_draft(t) for t in _pack(pieces, size, overlap)]


def _split(text: str, size: int, separators: list[str]) -> list[str]:
    if count_tokens(text) <= size or not separators:
        return [text] if text.strip() else []
    sep, rest = separators[0], separators[1:]
    parts = [p for p in text.split(sep) if p.strip()]
    if len(parts) == 1:
        return _split(text, size, rest)
    out = []
    for i, part in enumerate(parts):
        piece = part + (sep if i < len(parts) - 1 and sep.strip() else "")
        out.extend(_split(piece, size, rest) if count_tokens(piece) > size else [piece])
    # Words still too long for `size` can only be cut by token count.
    return [
        p
        for chunk in out
        for p in (_hard_cut(chunk, size) if count_tokens(chunk) > size else [chunk])
    ]


def _hard_cut(text: str, size: int) -> list[str]:
    return [d.text for d in fixed(text, size, 0)]


def _pack(pieces: list[str], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    tokens = 0
    for piece in pieces:
        n = count_tokens(piece)
        if current and tokens + n > size:
            chunks.append(_join(current))
            current, tokens = _tail(current, overlap)
            # The carried-over tail plus this piece may still be too big: drop the tail.
            if tokens + n > size:
                current, tokens = [], 0
        current.append(piece)
        tokens += n
    if current:
        chunks.append(_join(current))
    return chunks


def _tail(pieces: list[str], overlap: int) -> tuple[list[str], int]:
    """The last pieces of a chunk whose tokens fit in `overlap`."""
    out, tokens = [], 0
    for piece in reversed(pieces):
        n = count_tokens(piece)
        if tokens + n > overlap:
            break
        out.insert(0, piece)
        tokens += n
    return out, tokens


def _join(pieces: list[str]) -> str:
    return " ".join(p.strip() for p in pieces if p.strip())


# --- markdown -----------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)


def markdown(text: str, size: int, overlap: int) -> list[ChunkDraft]:
    """Split at headings first so a chunk never spans two sections, then recursively inside
    each section. Each chunk remembers its heading path, which is prepended for embedding."""
    out = []
    for path, body in _sections(text):
        for t in _pack(_split(body, size, SEPARATORS), size, overlap):
            out.append(_draft(t, heading=path))
    return out


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADING.finditer(text))
    sections = []
    if not matches or matches[0].start() > 0:
        intro = text[: matches[0].start() if matches else len(text)]
        if intro.strip():
            sections.append(("", intro))
    stack: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        level, title = len(m.group(1)), m.group(2)
        stack = [(lvl, t) for lvl, t in stack if lvl < level] + [(level, title)]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end]
        if body.strip():
            sections.append((" › ".join(t for _, t in stack), body))
    return sections


# --- semantic -----------------------------------------------------------------------------

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def semantic(text: str, size: int, overlap: int, embed: Embed) -> list[ChunkDraft]:
    """Embed every sentence and start a new chunk where the meaning shifts: where cosine
    similarity between neighbouring sentences drops well below its average. Groups that are
    still too big are split recursively. Costs one embedding per sentence."""
    sentences = [s.strip() for s in _SENTENCE.split(text) if s and s.strip()]
    if len(sentences) < 3:
        return recursive(text, size, overlap)
    vectors = embed(sentences)
    sims = [_cosine(a, b) for a, b in zip(vectors, vectors[1:], strict=False)]
    mean = sum(sims) / len(sims)
    std = math.sqrt(sum((s - mean) ** 2 for s in sims) / len(sims))
    groups, current = [], [sentences[0]]
    for sentence, sim in zip(sentences[1:], sims, strict=True):
        if std > 0 and sim < mean - std:
            groups.append(" ".join(current))
            current = []
        current.append(sentence)
    groups.append(" ".join(current))
    out = []
    for g in groups:
        out.extend(recursive(g, size, overlap) if count_tokens(g) > size else [_draft(g)])
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --- parent document ----------------------------------------------------------------------


def parent_document(text: str, size: int, overlap: int) -> list[ChunkDraft]:
    """Small chunks match questions precisely; the LLM gets the surrounding parent (4× size)
    for context. Children are what we embed and search; parent_text is what we show."""
    out = []
    for parent in recursive(text, size * 4, overlap):
        for child in recursive(parent.text, size, overlap):
            child.parent_text = parent.text
            out.append(child)
    return out


# --- entry point --------------------------------------------------------------------------


def chunk(
    text: str, *, strategy: str, size: int, overlap: int, embed: Embed | None = None
) -> list[ChunkDraft]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    if strategy == "fixed":
        return fixed(text, size, overlap)
    if strategy == "recursive":
        return recursive(text, size, overlap)
    if strategy == "markdown":
        return markdown(text, size, overlap)
    if strategy == "semantic":
        if embed is None:
            raise ValueError("semantic chunking needs an embed function")
        return semantic(text, size, overlap, embed)
    if strategy == "parent_document":
        return parent_document(text, size, overlap)
    raise ValueError(f"Unknown chunking strategy: {strategy}")


def _draft(text: str, heading: str = "") -> ChunkDraft:
    text = text.strip()
    return ChunkDraft(text=text, token_count=len(tokenize(text)), heading=heading)
