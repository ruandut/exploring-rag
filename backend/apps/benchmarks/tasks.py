"""benchmarks' Hatchet tasks: a parent run that fans out one child per case.

    benchmark-run ──▶ benchmark-case × N  (2 at a time per user)
         └── waits for all, then finalize(): aggregate + boundaries

Children never raise for a bad answer or an unreachable provider — they record the case as
failed (so "Retry failed cases" can re-run just those) and let the parent finish.
"""

from django.db import close_old_connections
from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context
from pydantic import BaseModel

from apps.jobs.hatchet import get_hatchet

from . import execution, services
from .models import BenchmarkRun, CaseResult

hatchet = get_hatchet()


class CaseInput(BaseModel):
    result_id: int
    user_id: int


@hatchet.task(
    name="benchmark-case",
    input_validator=CaseInput,
    execution_timeout="10m",
    retries=0,
    concurrency=ConcurrencyExpression(
        expression="string(input.user_id)",
        max_runs=2,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    ),
)
def benchmark_case(input: CaseInput, ctx: Context) -> dict:
    close_old_connections()
    try:
        result = CaseResult.objects.select_related("run__owner").get(pk=input.result_id)
        execution.execute(result)
        services.record_result(result)
        return {"status": result.status, "passed": result.passed}
    finally:
        close_old_connections()


class RunInput(BaseModel):
    run_id: int
    user_id: int
    result_ids: list[int]


@hatchet.task(name="benchmark-run", input_validator=RunInput, execution_timeout="60m", retries=0)
def benchmark_run(input: RunInput, ctx: Context) -> dict:
    close_old_connections()
    # Called from inside a task, these become child runs of this one in the Hatchet UI.
    benchmark_case.run_many(
        [
            benchmark_case.create_bulk_run_item(
                input=CaseInput(result_id=rid, user_id=input.user_id)
            )
            for rid in input.result_ids
        ],
        return_exceptions=True,
    )
    close_old_connections()
    # Anything a crashed child left pending counts as failed (retryable).
    CaseResult.objects.filter(pk__in=input.result_ids, status=CaseResult.Status.PENDING).update(
        status=CaseResult.Status.FAILED, error="The case did not finish", passed=False
    )
    run = services.finalize(BenchmarkRun.objects.get(pk=input.run_id))
    close_old_connections()
    return {"status": run.status}


TASKS = [benchmark_run, benchmark_case]
