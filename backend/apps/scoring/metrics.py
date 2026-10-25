"""The metric registry: every metric a suite can select or a boundary can reference.

Ids are shared with the frontend catalog (features/benchmarks/metrics.ts).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    id: str
    name: str
    kind: str  # retrieval | judge | operational
    applies_to: tuple[str, ...]  # case kinds it's computed for
    higher_is_better: bool = True
    uses_k: bool = False


METRICS: dict[str, Metric] = {
    m.id: m
    for m in [
        Metric("hit_rate", "Hit rate@k", "retrieval", ("qa",), uses_k=True),
        Metric("recall", "Recall@k", "retrieval", ("qa",), uses_k=True),
        Metric("precision", "Precision@k", "retrieval", ("qa",), uses_k=True),
        Metric("mrr", "MRR", "retrieval", ("qa",)),
        Metric("ndcg", "nDCG@k", "retrieval", ("qa",), uses_k=True),
        Metric("faithfulness", "Faithfulness", "judge", ("qa",)),
        Metric("answer_relevancy", "Answer relevancy", "judge", ("qa",)),
        Metric("answer_correctness", "Answer correctness", "judge", ("qa",)),
        Metric("context_precision", "Context precision", "judge", ("qa",)),
        Metric("context_recall", "Context recall", "judge", ("qa",)),
        Metric("citation_accuracy", "Citation accuracy", "judge", ("qa",)),
        # Always computed for refusal cases; selectable for boundaries.
        Metric("refusal_rate", "Refusal rate", "judge", ("refusal",)),
        Metric("ttft", "Time to first token (s)", "operational", ("qa", "refusal"), False),
        Metric("latency_total", "Total latency (s)", "operational", ("qa", "refusal"), False),
        Metric("tokens", "Answer tokens", "operational", ("qa", "refusal"), False),
        Metric("error_rate", "Error rate", "operational", ("qa", "refusal"), False),
    ]
}

# Selectable in the suite editor (operational metrics are always recorded).
SELECTABLE = [
    m.id for m in METRICS.values() if m.kind in ("retrieval", "judge") and m.id != "refusal_rate"
]

# Below this, a case's score counts as a failure for that case.
CASE_PASS_THRESHOLD = 0.5


def display_name(metric_id: str, k: int) -> str:
    m = METRICS[metric_id]
    return m.name.replace("@k", f"@{k}") if m.uses_k else m.name
