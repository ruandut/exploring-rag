"""Write-side logic for agents, and the entry point for starting an agent run."""

from django.db import transaction

from .models import Agent, default_rag_config

DEMO_AGENT = "demo"  # the canned-stream agent from spec 0001; needs no LLM


@transaction.atomic
def save_agent(user, *, data: dict, instance: Agent | None = None) -> Agent:
    agent = instance or Agent(owner=user)
    for field in ("name", "system_message"):
        if field in data:
            setattr(agent, field, data[field])
    if "rag_config" in data:
        agent.rag_config = {**default_rag_config(), **data["rag_config"]}
    agent.save()
    return agent


def snapshot(agent: Agent) -> dict:
    """The agent's configuration, frozen — benchmark runs keep it so old results stay
    meaningful after the agent is edited."""
    return {
        "id": agent.pk,
        "name": agent.name,
        "system_message": agent.system_message,
        "rag_config": {**default_rag_config(), **agent.rag_config},
    }


def from_snapshot(user, snap: dict) -> Agent:
    """An unsaved Agent rebuilt from a snapshot (runs from before 0010 also had connection,
    model and folders keys; those now come from the run's own target)."""
    return Agent(
        owner=user,
        name=snap["name"],
        system_message=snap["system_message"],
        rag_config=snap["rag_config"],
    )


async def astart_run(
    user,
    agent_key: str,
    messages: list[dict],
    *,
    embedding_id: int | None = None,
    connection_id: int | None = None,
    model: str = "",
) -> str:
    """Start an agent run on Hatchet and return its run id (stream it with the run id).

    agent_key is an Agent id, or "demo" for the canned demo agent. The chat decides what is
    searched (embedding_id; None = nothing) and which model answers (connection_id + model;
    None + "" = the default provider's chat model).
    """
    if agent_key == DEMO_AGENT:
        from apps.jobs.tasks.agent import AgentRunInput as DemoInput
        from apps.jobs.tasks.agent import demo_agent

        run = await demo_agent.aio_run_no_wait(
            DemoInput(user_id=user.id, agent_id=DEMO_AGENT, message=messages[-1]["content"])
        )
        return run.workflow_run_id

    from .tasks import AgentRunInput, agent_run

    run = await agent_run.aio_run_no_wait(
        AgentRunInput(
            user_id=user.id,
            agent_id=int(agent_key),
            messages=messages,
            embedding_id=embedding_id,
            connection_id=connection_id,
            model=model,
        )
    )
    return run.workflow_run_id
