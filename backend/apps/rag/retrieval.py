"""Answer-time retrieval: query → (optional transform) → search → (optional rerank) → chunks.

Search methods:
- dense    pgvector cosine distance. Casts to vector(N) so the partial HNSW index is used.
- keyword  Postgres full-text search (OR of the query's lexemes, ranked by ts_rank_cd).
- hybrid   both, merged with Reciprocal Rank Fusion — catches exact terms (codes, names) that
           embeddings blur, and paraphrases that keywords miss.
- mmr      dense candidates re-picked for diversity (Maximal Marginal Relevance).
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from django.db import connection

from apps.library import selectors as library_selectors

from .llm import Completer, parse_int_list
from .models import HNSW_DIMENSIONS, Chunk, EmbeddingIndex

RRF_K = 60  # standard constant; dampens the influence of exact rank positions
CANDIDATES = 20  # how many each method fetches before fusing / reranking
MMR_LAMBDA = 0.5  # 1.0 = pure relevance, 0.0 = pure diversity


@dataclass
class RetrievalConfig:
    method: str = "hybrid"  # dense | keyword | hybrid | mmr
    top_k: int = 5
    query_transform: str = "none"  # none | multi_query | hyde | step_back
    rerank: str = "none"  # none | llm


@dataclass
class Retrieved:
    chunk_id: int
    document_id: int
    document: str
    index: int
    heading: str
    text: str
    parent_text: str
    score: float

    @property
    def tag(self) -> str:
        """How the model cites it: [handbook.md#3]."""
        return f"{self.document}#{self.index}"

    def as_event(self) -> dict:
        return {
            "document": self.document,
            "chunk": self.index,
            "score": round(self.score, 4),
            "text": self.text,
        }


Ranked = list[tuple[int, float]]  # (chunk id, score), best first


def search(
    user,
    query: str,
    *,
    config: RetrievalConfig,
    index: EmbeddingIndex,
    folder_ids: Sequence[int] | None = None,
    embed: Callable[[list[str]], list[list[float]]],
    llm: Completer,
) -> list[Retrieved]:
    doc_ids = (
        library_selectors.document_ids_in_folders(user, list(folder_ids)) if folder_ids else None
    )
    if doc_ids == []:
        return []
    want = config.top_k * 3 if config.rerank == "llm" else config.top_k

    queries = [query]
    dense_text = {query: query}
    if config.query_transform == "multi_query":
        reply = llm.complete(
            "Write 3 different search queries that would find information to answer the "
            f"question below. One per line, no numbering.\n\nQuestion: {query}",
        )
        queries += [q.strip(" -•\t") for q in reply.splitlines() if q.strip()][:3]
    elif config.query_transform == "step_back":
        queries.append(
            llm.complete(
                "Rewrite this as a broader, more general question. "
                f"Reply with the question only.\n\n{query}",
            )
        )
    elif config.query_transform == "hyde":
        # Hypothetical Document Embeddings: embed a made-up answer, which looks more like the
        # passages we want than the question does. Keyword search still uses the question.
        dense_text[query] = llm.complete(
            f"Write a short passage (3 sentences) that answers this question:\n\n{query}",
        )

    # The query must be embedded by the index's own model — that's what `embed` is — and only
    # that index's chunks are searched, so vectors from different models never meet.
    vectors = embed([dense_text.get(q, q) for q in queries])
    scope = Scope(user.id, index.pk, doc_ids)
    ranked = (
        rrf(
            [
                _search_one(scope, q, v, config.method, want)
                for q, v in zip(queries, vectors, strict=True)
            ]
        )
        if len(queries) > 1
        else _search_one(scope, queries[0], vectors[0], config.method, want)
    )
    chunks = hydrate(ranked[:want])

    if config.rerank == "llm" and len(chunks) > 1:
        chunks = llm_rerank(llm, query, chunks)
    return chunks[: config.top_k]


@dataclass
class Scope:
    """Which chunks a search may see: one user's, in one embedding, optionally some documents."""

    owner_id: int
    index_id: int
    doc_ids: list[int] | None = None

    def sql(self) -> tuple[str, list]:
        where = "owner_id = %s AND embedding_index_id = %s"
        params: list = [self.owner_id, self.index_id]
        if self.doc_ids is not None:
            where += " AND document_id = ANY(%s)"
            params.append(self.doc_ids)
        return where, params


def _search_one(scope: Scope, query: str, vector: list[float], method: str, limit: int) -> Ranked:
    if method == "dense":
        return dense(scope, vector, limit)
    if method == "keyword":
        return keyword(scope, query, limit)
    if method == "hybrid":
        return rrf([dense(scope, vector, CANDIDATES), keyword(scope, query, CANDIDATES)])[:limit]
    if method == "mmr":
        return mmr(scope, vector, limit)
    raise ValueError(f"Unknown retrieval method: {method}")


def _vector_sql(dims: int) -> str:
    # Must match the expression in migration 0003 exactly, or Postgres can't use the index.
    return f"::vector({dims})" if dims in HNSW_DIMENSIONS else "::vector"


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vector) + "]"


def dense(scope: Scope, vector: list[float], limit: int) -> Ranked:
    dims = len(vector)
    cast = _vector_sql(dims)
    where, params = scope.sql()
    sql = f"""
        SELECT id, 1 - (embedding{cast} <=> %s{cast}) AS score
        FROM rag_chunk
        WHERE {where} AND dimensions = %s
        ORDER BY embedding{cast} <=> %s{cast}, id
        LIMIT %s
    """
    params = [_literal(vector), *params, dims, _literal(vector), limit]
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return [(row[0], float(row[1])) for row in cur.fetchall()]


def keyword(scope: Scope, query: str, limit: int) -> Ranked:
    # plainto_tsquery ANDs every word; we OR them so one rare exact term (an error code, a
    # name) is enough to match, and let ts_rank_cd reward chunks that match more of them.
    where, params = scope.sql()
    sql = f"""
        SELECT id, ts_rank_cd(search_vector, q) AS score
        FROM rag_chunk,
             to_tsquery('english', replace(plainto_tsquery('english', %s)::text, '&', '|')) q
        WHERE {where} AND search_vector @@ q
        ORDER BY score DESC, id
        LIMIT %s
    """
    params = [query, *params, limit]
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return [(row[0], float(row[1])) for row in cur.fetchall()]


def rrf(lists: Sequence[Ranked]) -> Ranked:
    """Reciprocal Rank Fusion: score = Σ 1 / (k + rank). Only ranks matter, so scores from
    different methods (cosine vs ts_rank) never need to be on the same scale."""
    scores: dict[int, float] = {}
    for ranked in lists:
        for rank, (chunk_id, _) in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def mmr(scope: Scope, vector: list[float], limit: int) -> Ranked:
    candidates = dense(scope, vector, CANDIDATES)
    if not candidates:
        return []
    embeddings = dict(
        Chunk.objects.filter(pk__in=[c for c, _ in candidates]).values_list("pk", "embedding")
    )
    relevance = dict(candidates)
    picked: Ranked = []
    remaining = [c for c, _ in candidates]
    while remaining and len(picked) < limit:

        def gain(cid: int) -> float:
            redundancy = max(
                (_cosine(embeddings[cid], embeddings[p]) for p, _ in picked), default=0.0
            )
            return MMR_LAMBDA * relevance[cid] - (1 - MMR_LAMBDA) * redundancy

        best = max(remaining, key=gain)
        picked.append((best, relevance[best]))
        remaining.remove(best)
    return picked


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def hydrate(ranked: Ranked) -> list[Retrieved]:
    rows = (
        Chunk.objects.filter(pk__in=[c for c, _ in ranked])
        .select_related("document")
        .defer("embedding", "search_vector")
    )
    by_id = {c.pk: c for c in rows}
    out = []
    for chunk_id, score in ranked:
        c = by_id.get(chunk_id)
        if c is None:
            continue
        out.append(
            Retrieved(
                chunk_id=c.pk,
                document_id=c.document_id,
                document=c.document.name,
                index=c.index,
                heading=c.heading,
                text=c.text,
                parent_text=c.parent_text,
                score=score,
            )
        )
    return out


def llm_rerank(llm: Completer, query: str, chunks: list[Retrieved]) -> list[Retrieved]:
    """Ask the LLM to order the candidates by relevance. Falls back to the original order."""
    passages = "\n\n".join(f"[{i}] {c.text[:600]}" for i, c in enumerate(chunks))
    reply = llm.complete(
        f"Question: {query}\n\nPassages:\n{passages}\n\nReturn a JSON array of passage numbers "
        "ordered from most to least relevant to the question. Reply with the array only.",
        max_tokens=100,
    )
    order = parse_int_list(reply) or []
    seen = [i for i in dict.fromkeys(order) if 0 <= i < len(chunks)]
    return [chunks[i] for i in seen] + [c for i, c in enumerate(chunks) if i not in seen]
