"""Starting runs, recording case results, and turning them into a summary.

Flow: start_runs() creates the run + one pending CaseResult per case and starts the
`benchmark-run` Hatchet task, which fans out a `benchmark-case` child per result and calls
finalize() when they've all finished. retry_failed() does the same for just the failed ones
(errored or scored below the case pass threshold).
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.agents import selectors as agent_selectors
from apps.agents import services as agent_services
from apps.evals import selectors as eval_selectors
from apps.evals.models import EvalSuite
from apps.providers import selectors as provider_selectors
from apps.rag import selectors as rag_selectors
from apps.rag.models import EmbeddingIndex
from apps.realtime.events import send_to_user
from apps.scoring import aggregate
from apps.scoring.metrics import METRICS

from .models import BenchmarkRun, CaseResult

log = logging.getLogger(__name__)

OPERATIONAL = {
    "ttft": "ttft_ms",
    "latency_total": "latency_ms",
    "tokens": "tokens",
    "tokens_per_second": "tokens_per_second",
    "waiting_time": "waiting_ms",
    "search_time": "search_ms",
    "reasoning_time": "reasoning_ms",
    "writing_time": "writing_ms",
    "judge_time": "judge_ms",
}


class InvalidTarget(Exception):
    pass


def describe_target(user, target: dict) -> tuple[str, str, dict]:
    """(kind, label, snapshot) for
    {"kind": "agent", "agent": id, "embedding": id | None, "connection": id | None, "model": ""}
    or {"kind": "model", "connection": id | None, "model": "name"}.

    Since spec 0010 an agent run also names what it searches and which model answers — like a
    chat — so two runs can compare embeddings (or models) with the same agent."""
    if target.get("kind") == "agent":
        try:
            agent = agent_selectors.get_agent(user, int(target["agent"]))
        except (KeyError, ValueError, LookupError) as exc:
            raise InvalidTarget("Unknown agent") from exc
        except Exception as exc:  # Agent.DoesNotExist
            raise InvalidTarget("Unknown agent") from exc
        embedding = _target_embedding(user, target)
        source, model, connection = _target_model(user, target, required=False)
        snap = {
            **agent_services.snapshot(agent),
            # Frozen so the run stays readable after the embedding is edited or deleted.
            "embedding": embedding_snapshot(embedding),
            "connection": connection.pk if connection else None,
            "connection_name": source,
            "model": model,
            # The model that actually answers, resolved now — what Model speed groups by.
            "model_label": _model_label(user, source, model),
        }
        label = f"{agent.name} · {embedding.name if embedding else 'no embedding'}"
        return BenchmarkRun.TargetKind.AGENT, label, snap

    if target.get("kind") == "model":
        source, model, connection = _target_model(user, target, required=True)
        model = model or provider_selectors.get_provider_config(user).chat_model
        snap = {
            "connection": connection.pk if connection else None,
            "connection_name": source,
            "model": model,
            "model_label": f"{source} · {model}",
        }
        return BenchmarkRun.TargetKind.MODEL, f"{source} · {model} (bare)", snap

    raise InvalidTarget("A target is an agent or a bare model")


def _model_label(user, source: str, model: str) -> str:
    """E.g. "Default provider · fake-chat" — an agent's empty model resolved to the default."""
    if not model:
        config = provider_selectors.get_provider_config(user)
        model = config.chat_model if config else ""
    return f"{source} · {model}"


def embedding_snapshot(index: EmbeddingIndex | None) -> dict | None:
    if index is None:
        return None
    return {
        "id": index.pk,
        "name": index.name,
        "model": index.model,
        "dimensions": index.dimensions,
        "strategy": index.strategy,
        "chunk_size": index.chunk_size,
        "chunk_overlap": index.chunk_overlap,
    }


def _target_embedding(user, target: dict) -> EmbeddingIndex | None:
    if "embedding" not in target:
        return rag_selectors.default_embedding(user)
    if target["embedding"] is None:
        return None
    try:
        return rag_selectors.get_embedding(user, int(target["embedding"]))
    except (EmbeddingIndex.DoesNotExist, ValueError, TypeError) as exc:
        raise InvalidTarget("Unknown embedding") from exc


def _target_model(user, target: dict, *, required: bool):
    """(source label, model, connection) — the default provider when no connection."""
    model = str(target.get("model", "") or "").strip()
    connection = None
    if target.get("connection"):
        try:
            connection = provider_selectors.get_connection(user, int(target["connection"]))
        except Exception as exc:
            raise InvalidTarget("Unknown connection") from exc
        if not model:
            raise InvalidTarget("Pick a model for this connection")
    elif required and provider_selectors.get_provider_config(user) is None:
        raise InvalidTarget("No default provider configured")
    return (connection.name if connection else "Default provider"), model, connection


@transaction.atomic
def start_runs(user, suite: EvalSuite, targets: list[dict]) -> list[BenchmarkRun]:
    """One run per target; two targets share a compare group (side-by-side)."""
    if not 1 <= len(targets) <= 2:
        raise InvalidTarget("Run against one target, or two to compare")
    snapshot = eval_selectors.snapshot(suite)
    if not snapshot["cases"]:
        raise InvalidTarget("The suite has no cases")
    group = BenchmarkRun.new_group() if len(targets) == 2 else None
    runs = []
    for target in targets:
        kind, label, target_snap = describe_target(user, target)
        run = BenchmarkRun.objects.create(
            owner=user,
            suite=suite,
            suite_snapshot=snapshot,
            target_kind=kind,
            target_label=label,
            target_snapshot=target_snap,
            compare_group=group,
            summary={"done": 0, "total": len(snapshot["cases"]), "failed_cases": 0},
        )
        CaseResult.objects.bulk_create(
            CaseResult(run=run, position=i, case=c) for i, c in enumerate(snapshot["cases"])
        )
        runs.append(run)
        transaction.on_commit(
            lambda run=run: _launch(run, list(run.results.values_list("pk", flat=True)))
        )
    return runs


@transaction.atomic
def retry_failed(run: BenchmarkRun) -> int:
    # "Failed" means the same here as on the case chip: errored *or* scored below the threshold.
    # Re-asking a below-threshold case is worth it — real models and judges aren't deterministic.
    failed = list(run.results.exclude(passed=True))
    if not failed:
        return 0
    CaseResult.objects.filter(pk__in=[r.pk for r in failed]).update(
        status=CaseResult.Status.PENDING, error="", passed=None
    )
    # Also how a stopped run resumes: its stopped cases aren't passed, so they re-run too.
    run.status = BenchmarkRun.Status.RUNNING
    run.finished_at = None
    run.save(update_fields=["status", "finished_at"])
    transaction.on_commit(lambda: _launch(run, [r.pk for r in failed]))
    return len(failed)


def _launch(run: BenchmarkRun, result_ids: list[int]) -> None:
    from .tasks import RunInput, benchmark_run

    ref = benchmark_run.run_no_wait(
        RunInput(run_id=run.pk, user_id=run.owner_id, result_ids=result_ids)
    )
    BenchmarkRun.objects.filter(pk=run.pk).update(hatchet_run_id=ref.workflow_run_id)
    _progress(run)


@transaction.atomic
def cancel_run(run: BenchmarkRun) -> bool:
    """Stop a running run (spec 0012). False if it had already finished.

    The database is the source of truth: the run and every pending case flip to cancelled
    here, so a child that still starts — or one mid-answer polling `is_cancelled` — stops
    even if Hatchet's cancel arrives late. Cancelling the parent in Hatchet is the fast
    path that drops the queued children."""
    if not BenchmarkRun.objects.filter(pk=run.pk, status=BenchmarkRun.Status.RUNNING).update(
        status=BenchmarkRun.Status.CANCELLED
    ):
        return False
    run.results.filter(status=CaseResult.Status.PENDING).update(
        status=CaseResult.Status.CANCELLED, passed=None
    )
    run.refresh_from_db()
    results = list(run.results.all())
    finished = [r for r in results if r.status != CaseResult.Status.CANCELLED]
    summary, _ = _summary(run, finished)
    # A stopped run never passes: its boundaries aren't checked, its metrics are partial.
    for b in summary["boundaries"]:
        b["passed"], b["margin"] = None, None
    run.summary = {
        **summary,
        "total": len(results),
        "stopped_cases": len(results) - len(finished),
        "partial": True,
    }
    run.finished_at = timezone.now()
    run.save(update_fields=["summary", "finished_at"])
    hatchet_run_id = run.hatchet_run_id
    transaction.on_commit(lambda: _cancel_in_hatchet(hatchet_run_id))
    send_to_user(
        run.owner_id, {"type": "benchmark.completed", "run_id": run.pk, "status": run.status}
    )
    return True


def _cancel_in_hatchet(hatchet_run_id: str) -> None:
    if not hatchet_run_id:
        return
    from apps.jobs.hatchet import get_hatchet

    try:
        get_hatchet().runs.cancel(hatchet_run_id)
    except Exception:  # best effort: the database flag already stops every case
        log.exception("Couldn't cancel Hatchet run %s", hatchet_run_id)


def is_case_cancelled(result_id: int) -> bool:
    """True once the case's run was stopped (its case is no longer pending)."""
    return not CaseResult.objects.filter(pk=result_id, status=CaseResult.Status.PENDING).exists()


# Every column a case result writes back (all but its identity and what it was asked).
_RESULT_FIELDS = [
    f.attname
    for f in CaseResult._meta.concrete_fields
    if f.attname not in ("id", "run_id", "position", "case")
]


def record_result(result: CaseResult) -> None:
    # Saved only while the case is still pending: a case that finishes after its run was
    # stopped keeps its "Stopped" status instead of quietly getting a result (spec 0012).
    saved = CaseResult.objects.filter(pk=result.pk, status=CaseResult.Status.PENDING).update(
        **{f: getattr(result, f) for f in _RESULT_FIELDS}
    )
    if not saved:
        return
    run = result.run
    send_to_user(
        run.owner_id,
        {
            "type": "benchmark.case",
            "run_id": run.pk,
            "result_id": result.pk,
            "status": result.status,
            "passed": result.passed,
        },
    )
    _progress(run)


def _progress(run: BenchmarkRun) -> None:
    results = run.results.all()
    done = results.exclude(status=CaseResult.Status.PENDING).count()
    send_to_user(
        run.owner_id,
        {"type": "benchmark.progress", "run_id": run.pk, "done": done, "total": results.count()},
    )


def finalize(run: BenchmarkRun) -> BenchmarkRun:
    """Aggregate every metric, check the boundaries, and decide pass / fail.

    A run passes only when every case passed *and* every applicable boundary holds. Boundaries
    are optional, cases aren't — so the run verdict can never say "Passed" while the case list
    shows failures.
    """
    run.refresh_from_db(fields=["status"])
    if run.status == BenchmarkRun.Status.CANCELLED:
        return run  # stopped meanwhile: cancel_run already summarised it
    summary, passed = _summary(run, list(run.results.all()))
    run.summary = summary
    run.status = BenchmarkRun.Status.PASSED if passed else BenchmarkRun.Status.FAILED
    run.finished_at = timezone.now()
    run.save(update_fields=["summary", "status", "finished_at"])
    send_to_user(
        run.owner_id, {"type": "benchmark.completed", "run_id": run.pk, "status": run.status}
    )
    return run


def _summary(run: BenchmarkRun, results: list[CaseResult]) -> tuple[dict, bool]:
    """Aggregate the given cases' metrics and check the boundaries: (summary, passed)."""
    scored = [r for r in results if r.status == CaseResult.Status.DONE]
    errored = [r for r in results if r.status == CaseResult.Status.FAILED]
    failed = [r for r in results if not r.passed]  # errored or below the case threshold

    metric_ids = list(run.suite_snapshot["metrics"])
    if any(r.case["kind"] == "refusal" for r in results):
        metric_ids.append("refusal_rate")
    metrics = {}
    for metric_id in metric_ids:
        values = [r.scores.get(metric_id) for r in scored]
        values = [v for v in values if v is not None]
        metrics[metric_id] = aggregate.summarise(values)
    for metric_id, field in OPERATIONAL.items():
        values = [getattr(r, field) for r in scored if getattr(r, field) is not None]
        if field.endswith("_ms"):
            values = [v / 1000 for v in values]  # report seconds
        metrics[metric_id] = aggregate.summarise(values)
    error_rate = len(errored) / len(results) if results else 0.0
    metrics["error_rate"] = aggregate.summarise([error_rate])

    boundaries = [
        aggregate.check(
            b["metric"], b["aggregate"], b["comparator"], b["value"], metrics.get(b["metric"])
        ).as_dict()
        for b in run.suite_snapshot["boundaries"]
    ]
    passed = not failed and all(b["passed"] is not False for b in boundaries)

    summary = {
        "done": len(results),
        "total": len(results),
        "failed_cases": len(failed),
        "errored_cases": len(errored),
        "passed_cases": len(results) - len(failed),
        "metrics": metrics,
        "boundaries": boundaries,
    }
    return summary, passed


def metric_label(metric_id: str, k: int) -> str:
    from apps.scoring.metrics import display_name

    return display_name(metric_id, k) if metric_id in METRICS else metric_id
