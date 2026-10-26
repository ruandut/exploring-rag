"""agents' Hatchet task. Auto-discovered by the worker via TASKS."""

import json
import time
from typing import Literal

from django.core.exceptions import ObjectDoesNotExist
from django.db import close_old_connections
from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context
from hatchet_sdk.exceptions import NonRetryableException
from pydantic import BaseModel

from apps.jobs.hatchet import get_hatchet
from apps.providers import selectors as provider_selectors
from apps.providers.llm import ProviderError
from apps.rag import selectors as rag_selectors

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
    embedding_id: int | None = None  # what to search; None = answer from the model alone
    connection_id: int | None = None  # None = the default provider
    model: str = ""  # "" = the provider's chat model


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
        agent = Agent.objects.select_related("owner").get(pk=input.agent_id, owner_id=input.user_id)
        user = agent.owner
        result = runner.run(
            user=user,
            agent=agent,
            messages=[m.model_dump() for m in input.messages],
            emit=emit,
            is_cancelled=lambda: ctx.is_cancelled,
            embedding=(
                rag_selectors.get_embedding(user, input.embedding_id)
                if input.embedding_id
                else None
            ),
            connection=(
                provider_selectors.get_connection(user, input.connection_id)
                if input.connection_id
                else None
            ),
            model=input.model,
        )
        emit({"type": "agent.done", "model": result.model, "mode": result.mode})
        return {"model": result.model, "mode": result.mode, "chars": len(result.answer)}
    except runner.Cancelled:
        return {"cancelled": True}
    except (ProviderError, ValueError, ObjectDoesNotExist) as exc:
        detail = str(exc)
        emit({"type": "agent.error", "detail": detail})
        raise NonRetryableException(detail) from exc
    finally:
        close_old_connections()


TASKS = [agent_run]
