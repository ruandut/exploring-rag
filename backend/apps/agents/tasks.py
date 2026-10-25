"""agents' Hatchet task. Auto-discovered by the worker via TASKS."""

import json
import time
from typing import Literal

from django.db import close_old_connections
from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context
from hatchet_sdk.exceptions import NonRetryableException
from openai import OpenAIError
from pydantic import BaseModel

from apps.jobs.hatchet import get_hatchet
from apps.providers.services import error_message

from . import runner
from .models import Agent

hatchet = get_hatchet()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AgentRunInput(BaseModel):
    user_id: int
    agent_id: int
    messages: list[ChatMessage]


@hatchet.task(
    name="agent-run",
    input_validator=AgentRunInput,
    execution_timeout="10m",
    # A half-streamed answer can't be resumed, so no retries: the user just asks again.
    retries=0,
    concurrency=ConcurrencyExpression(
        expression="string(input.user_id)",
        max_runs=2,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    ),
)
def agent_run(input: AgentRunInput, ctx: Context) -> dict:
    close_old_connections()
    # Stream chunks published before the consumer subscribes aren't replayed; give it a moment.
    time.sleep(0.3)

    def emit(event: dict) -> None:
        ctx.put_stream(json.dumps(event))

    try:
        agent = Agent.objects.select_related("connection", "owner").get(
            pk=input.agent_id, owner_id=input.user_id
        )
        result = runner.run(
            user=agent.owner,
            agent=agent,
            messages=[m.model_dump() for m in input.messages],
            emit=emit,
            is_cancelled=lambda: ctx.is_cancelled,
        )
        emit({"type": "agent.done", "model": result.model, "mode": result.mode})
        return {"model": result.model, "mode": result.mode, "chars": len(result.answer)}
    except runner.Cancelled:
        return {"cancelled": True}
    except (OpenAIError, ValueError, Agent.DoesNotExist) as exc:
        detail = error_message(exc) if isinstance(exc, OpenAIError) else str(exc)
        emit({"type": "agent.error", "detail": detail})
        raise NonRetryableException(detail) from exc
    finally:
        close_old_connections()


TASKS = [agent_run]
