"""Starting runs, recording case results, and turning them into a summary.

Flow: start_runs() creates the run + one pending CaseResult per case and starts the
`benchmark-run` Hatchet task, which fans out a `benchmark-case` child per result and calls
finalize() when they've all finished. retry_failed() does the same for just the failed ones.
"""

from django.db import transaction
from django.utils import timezone

from apps.agents import selectors as agent_selectors
from apps.agents import services as agent_services
from apps.evals import selectors as eval_selectors
from apps.evals.models import EvalSuite
from apps.providers import selectors as provider_selectors
from apps.realtime.events import send_to_user
from apps.scoring import aggregate
from apps.scoring.metrics import METRICS

from .models import BenchmarkRun, CaseResult

OPERATIONAL = {"ttft": "ttft_ms", "latency_total": "latency_ms", "tokens": "tokens"}


class InvalidTarget(Exception):
    pass


def describe_target(user, target: dict) -> tuple[str, str, dict]:
    """(kind, label, snapshot) for {"kind": "agent", "agent": id} or
    {"kind": "model", "connection": id | None, "model": "name"}."""
    if target.get("kind") == "agent":
        try:
            agent = agent_selectors.get_agent(user, int(target["agent"]))
        except (KeyError, ValueError, LookupError) as exc:
            raise InvalidTarget("Unknown agent") from exc
        except Exception as exc:  # Agent.DoesNotExist
            raise InvalidTarget("Unknown agent") from exc
        return BenchmarkRun.TargetKind.AGENT, agent.name, agent_services.snapshot(agent)

    if target.get("kind") == "model":
        model = str(target.get("model", "")).strip()
        connection = None
        if target.get("connection"):
            try:
                connection = provider_selectors.get_connection(user, int(target["connection"]))
            except Exception as exc:
                raise InvalidTarget("Unknown connection") from exc
        elif provider_selectors.get_provider_config(user) is None:
            raise InvalidTarget("No default provider configured")
        source = connection.name if connection else "Default provider"
        if not model:
            if connection:
                raise InvalidTarget("Pick a model for this connection")
            model = provider_selectors.get_provider_config(user).chat_model
        snap = {
            "connection": connection.pk if connection else None,
            "connection_name": source,
            "model": model,
        }
        return BenchmarkRun.TargetKind.MODEL, f"{source} · {model} (bare)", snap

    raise InvalidTarget("A target is an agent or a bare model")


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
    failed = list(run.results.filter(status=CaseResult.Status.FAILED))
    if not failed:
        return 0
    CaseResult.objects.filter(pk__in=[r.pk for r in failed]).update(
        status=CaseResult.Status.PENDING, error="", passed=None
    )
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


def record_result(result: CaseResult) -> None:
    result.save()
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
    """Aggregate every metric, check the boundaries, and decide pass / fail."""
    results = list(run.results.all())
    scored = [r for r in results if r.status == CaseResult.Status.DONE]
    failed = [r for r in results if r.status == CaseResult.Status.FAILED]

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
        if metric_id in ("ttft", "latency_total"):
            values = [v / 1000 for v in values]  # report seconds
        metrics[metric_id] = aggregate.summarise(values)
    error_rate = len(failed) / len(results) if results else 0.0
    metrics["error_rate"] = aggregate.summarise([error_rate])

    boundaries = [
        aggregate.check(
            b["metric"], b["aggregate"], b["comparator"], b["value"], metrics.get(b["metric"])
        ).as_dict()
        for b in run.suite_snapshot["boundaries"]
    ]
    passed = not failed and all(b["passed"] is not False for b in boundaries)

    run.summary = {
        "done": len(results),
        "total": len(results),
        "failed_cases": len(failed),
        "passed_cases": sum(1 for r in scored if r.passed),
        "metrics": metrics,
        "boundaries": boundaries,
    }
    run.status = BenchmarkRun.Status.PASSED if passed else BenchmarkRun.Status.FAILED
    run.finished_at = timezone.now()
    run.save(update_fields=["summary", "status", "finished_at"])
    send_to_user(
        run.owner_id, {"type": "benchmark.completed", "run_id": run.pk, "status": run.status}
    )
    return run


def metric_label(metric_id: str, k: int) -> str:
    from apps.scoring.metrics import display_name

    return display_name(metric_id, k) if metric_id in METRICS else metric_id
