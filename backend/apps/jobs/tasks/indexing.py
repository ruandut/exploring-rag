"""Demo indexing job: proves the API → Hatchet → worker → websocket loop.

Spec 0003 replaces the fake loop with parse → chunk → embed → upsert into pgvector.
"""

import asyncio

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context
from pydantic import BaseModel

from apps.realtime.events import asend_to_user

from ..hatchet import get_hatchet

hatchet = get_hatchet()


class DemoIndexInput(BaseModel):
    user_id: int
    steps: int = 10


@hatchet.task(
    name="demo-index",
    input_validator=DemoIndexInput,
    retries=2,
    backoff_factor=2.0,
    # At most 2 indexing runs per user at a time; extra runs wait their turn instead of
    # starving other users. The CEL expression groups runs by the input's user_id.
    concurrency=ConcurrencyExpression(
        expression="string(input.user_id)",
        max_runs=2,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    ),
)
async def demo_index(input: DemoIndexInput, ctx: Context) -> dict:
    run_id = ctx.workflow_run_id
    for step in range(1, input.steps + 1):
        await asyncio.sleep(0.4)
        await asend_to_user(
            input.user_id,
            {
                "type": "job.progress",
                "run_id": run_id,
                "job": "demo-index",
                "step": step,
                "total": input.steps,
                "message": f"Embedding chunk {step}/{input.steps}",
            },
        )
    await asend_to_user(
        input.user_id, {"type": "job.completed", "run_id": run_id, "job": "demo-index"}
    )
    return {"chunks_indexed": input.steps}
