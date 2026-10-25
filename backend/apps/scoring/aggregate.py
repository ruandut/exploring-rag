"""Aggregating per-case values and checking boundaries."""

import math
from dataclasses import asdict, dataclass

AGGREGATES = ("mean", "p50", "p95")
COMPARATORS = {"gte": "≥", "lte": "≤"}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0..100) — simple and exact for small samples."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def summarise(values: list[float]) -> dict:
    return {
        "mean": mean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "n": len(values),
    }


@dataclass
class BoundaryResult:
    metric: str
    aggregate: str
    comparator: str
    value: float
    actual: float | None
    passed: bool | None  # None = skipped (metric not applicable, e.g. retrieval on a bare model)
    margin: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def check(
    metric: str, aggregate: str, comparator: str, value: float, stats: dict | None
) -> BoundaryResult:
    actual = stats.get(aggregate) if stats else None
    if actual is None:
        return BoundaryResult(metric, aggregate, comparator, value, None, None, None)
    margin = actual - value if comparator == "gte" else value - actual
    # Round so 0.8 - 0.9 reads -0.10, not -0.09999999999999998.
    margin = round(margin, 6)
    return BoundaryResult(metric, aggregate, comparator, value, actual, margin >= 0, margin)
