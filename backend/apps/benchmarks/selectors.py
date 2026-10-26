"""Read queries for benchmarks."""

from apps.scoring import aggregate

from .models import BenchmarkRun, CaseResult


def model_speed(owner) -> list[dict]:
    """How fast each model answered, across all of the owner's finished runs (spec 0011).

    Grouped by the model that actually answered, so agent runs and bare runs of one model
    pool together — it's the model's speed, not the agent's. Only finished cases with
    timings count (failed cases and cases from before spec 0011 are left out). Fastest
    first, by typical tokens per second."""
    cases = (
        CaseResult.objects.filter(
            run__owner=owner,
            status=CaseResult.Status.DONE,
            latency_ms__isnull=False,
        )
        .exclude(run__status=BenchmarkRun.Status.RUNNING)
        .select_related("run")
        .only(
            "run__id",
            "run__target_label",
            "run__target_snapshot",
            "ttft_ms",
            "latency_ms",
            "tokens_per_second",
        )
    )
    groups: dict[str, dict] = {}
    for c in cases:
        label = c.run.target_snapshot.get("model_label") or c.run.target_label
        g = groups.setdefault(label, {"runs": set(), "ttft": [], "latency": [], "tps": []})
        g["runs"].add(c.run.pk)
        if c.ttft_ms is not None:
            g["ttft"].append(c.ttft_ms / 1000)
        g["latency"].append(c.latency_ms / 1000)
        if c.tokens_per_second is not None:
            g["tps"].append(c.tokens_per_second)

    rows = [
        {
            "model": label,
            "runs": len(g["runs"]),
            "cases": len(g["latency"]),
            "ttft_p50": aggregate.percentile(g["ttft"], 50),
            "latency_p95": aggregate.percentile(g["latency"], 95),
            "tokens_per_second_p50": aggregate.percentile(g["tps"], 50),
        }
        for label, g in groups.items()
    ]
    # Models with no measurable speed go last.
    rows.sort(key=lambda r: -(r["tokens_per_second_p50"] or -1))
    return rows
