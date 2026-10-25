"""Retrieval metrics: exact maths over what was retrieved vs. what should have been.

Relevance is decided by *document* (plus an optional evidence snippet), never by chunk number,
because chunk numbers change whenever a document is re-indexed:

    a retrieved chunk is relevant  ⇔  its document is a relevant document
                                       and (no evidence given, or the chunk contains it)

Every function returns (value, explanation) so the UI can show its working.
"""

import math
from dataclasses import dataclass


@dataclass
class Gold:
    documents: list[str]  # names of the documents that hold the answer
    evidence: str = ""  # optional text the relevant chunk must contain

    def is_relevant(self, document: str, text: str) -> bool:
        if document not in self.documents:
            return False
        return not self.evidence or _norm(self.evidence) in _norm(text)


@dataclass
class Item:
    document: str
    text: str


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def relevance(retrieved: list[Item], gold: Gold) -> list[bool]:
    return [gold.is_relevant(i.document, i.text) for i in retrieved]


def hit_rate(retrieved: list[Item], gold: Gold, k: int) -> tuple[float, str]:
    hit = any(relevance(retrieved[:k], gold))
    return (
        (1.0, f"a relevant chunk is in the top {k}")
        if hit
        else (0.0, f"no relevant chunk in the top {k}")
    )


def recall(retrieved: list[Item], gold: Gold, k: int) -> tuple[float, str]:
    """Fraction of the relevant *documents* that had a relevant chunk in the top k."""
    found = {
        i.document
        for i, rel in zip(retrieved[:k], relevance(retrieved[:k], gold), strict=True)
        if rel
    }
    total = len(set(gold.documents))
    return len(found) / total, f"{len(found)} of {total} relevant documents retrieved (top {k})"


def precision(retrieved: list[Item], gold: Gold, k: int) -> tuple[float, str]:
    rel = sum(relevance(retrieved[:k], gold))
    return rel / k, f"{rel} of the top {k} slots hold a relevant chunk"


def mrr(retrieved: list[Item], gold: Gold, k: int | None = None) -> tuple[float, str]:
    for rank, rel in enumerate(relevance(retrieved, gold), start=1):
        if rel:
            return 1 / rank, f"first relevant chunk at rank {rank} → 1/{rank}"
    return 0.0, "no relevant chunk retrieved"


def ndcg(retrieved: list[Item], gold: Gold, k: int) -> tuple[float, str]:
    """Binary-relevance nDCG@k: DCG of the actual order ÷ DCG of the best possible order of the
    same retrieved chunks. 1.0 means every relevant chunk was ranked above every irrelevant one."""
    rels = relevance(retrieved[:k], gold)
    dcg = sum(1 / math.log2(i + 2) for i, r in enumerate(rels) if r)
    ideal = sum(1 / math.log2(i + 2) for i in range(sum(rels)))
    if ideal == 0:
        return 0.0, f"no relevant chunk in the top {k}"
    return dcg / ideal, f"DCG {dcg:.3f} ÷ ideal {ideal:.3f}"


FUNCTIONS = {
    "hit_rate": hit_rate,
    "recall": recall,
    "precision": precision,
    "mrr": mrr,
    "ndcg": ndcg,
}


def score(metric_id: str, retrieved: list[Item], gold: Gold, k: int) -> tuple[float, str]:
    return FUNCTIONS[metric_id](retrieved, gold, k)
