"""The agent loop: an LLM that decides when to search the user's documents.

    messages ──▶ LLM (with the search_documents tool) ──▶ wants a search? ──yes──▶ retrieve,
        ▲                                                       │               add results
        └───────────────────────────────────────────────────────┘                    │
                                                                no ──▶ streamed answer ◀┘

Every step is reported through `emit` (agent.thinking / tool_call / retrieval / token), which the
Hatchet task turns into stream chunks for the browser. Those events are the same whichever
provider answers: the loop talks to a providers adapter (spec 0008), which turns OpenAI-,
Anthropic- or Google-specific streams into neutral Thinking / Text / ToolCall / Done events.

Models that can't call tools (many small local models) fall back to classic "retrieve then
answer" RAG: search once with the question, put the results in the prompt, stream the answer.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from apps.providers import services as provider_services
from apps.providers.llm import (
    Cancelled,
    Done,
    ProviderError,
    Text,
    Thinking,
    Tool,
    ToolCall,
    ToolsUnsupported,
)
from apps.providers.models import Connection
from apps.rag import generation, retrieval
from apps.rag.embedding import make_embedder
from apps.rag.models import EmbeddingIndex

from .models import Agent

MAX_STEPS = 4  # tool rounds before the model must answer
REFUSED = "The model declined to answer"

SEARCH_TOOL = Tool(
    name="search_documents",
    description="Search the user's documents for passages relevant to a query.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look for — a question or keywords.",
            }
        },
        "required": ["query"],
    },
)

Emit = Callable[[dict], None]

__all__ = ["Cancelled", "RunResult", "run"]  # Cancelled is re-exported for the agent-run task


@dataclass
class RunResult:
    answer: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    model: str = ""
    # "agentic"; "pipeline" when the model can't call tools; "model" when nothing is searched
    mode: str = "agentic"


def run(
    *,
    user,
    agent: Agent,
    messages: list[dict],
    emit: Emit,
    is_cancelled: Callable[[], bool] = lambda: False,
    embedding: EmbeddingIndex | None = None,
    connection: Connection | None = None,
    model: str = "",
) -> RunResult:
    """Answer with the agent's RAG pipeline, searching `embedding` (None: no search at all —
    the model answers alone) and answering with connection + model (None + "": the default
    provider's chat model). The chat picks all three (spec 0010)."""
    target = provider_services.chat_target(user, connection=connection, model=model)
    result = RunResult(model=target.label)
    question = messages[-1]["content"]
    cfg = agent.rag_config
    strategy = cfg.get("generation", "cited")
    search_cfg = retrieval.RetrievalConfig(
        method=cfg.get("retrieval", "hybrid"),
        top_k=int(cfg.get("top_k", 5)),
        query_transform=cfg.get("query_transform", "none"),
        rerank=cfg.get("rerank", "none"),
    )
    # The query is embedded by the embedding's own model and endpoint — vectors are only
    # comparable with vectors from the same model — whichever model writes the answer.
    embed = (
        make_embedder(provider_services.adapter_for(user, embedding.connection), embedding.model)
        if embedding
        else None
    )
    turn = _Turn(target, emit, result, is_cancelled, agent.effort or "high")

    def do_search(query: str) -> list[retrieval.Retrieved]:
        if embed is None:
            return []
        return retrieval.search(
            user, query, config=search_cfg, index=embedding, embed=embed, llm=target
        )

    def search_tool(query: str) -> str:
        result.tool_calls.append({"tool": "search_documents", "args": {"query": query}})
        emit({"type": "agent.tool_call", "tool": "search_documents", "args": {"query": query}})
        if embed is None:
            text, used = "Document search is unavailable: no embedding is selected.", []
        else:
            text, used = generation.tool_result(
                strategy, question, do_search(query), llm=target, research=do_search
            )
        events = [c.as_event() for c in used]
        result.retrieved.extend(events)
        emit({"type": "agent.retrieval", "chunks": events})
        return text

    # Neutral history (see providers/llm/base.py): append-only, never edited.
    history = [{"role": m["role"], "content": m["content"]} for m in messages]

    if embedding is None:
        # Nothing to search: no tool, no RAG instructions — just the agent and the model.
        result.mode = "model"
        turn(agent.system_message.strip(), history, None)
        return result

    system = "\n\n".join(
        p for p in (agent.system_message.strip(), generation.system_instructions(strategy)) if p
    )
    try:
        _agentic(turn, system, history, search_tool, question)
    except ToolsUnsupported:
        result.mode = "pipeline"
        note = "This model can't call tools, so I searched once with your question.\n"
        result.thinking += note
        emit({"type": "agent.thinking", "text": note})
        context = search_tool(question)
        history[-1] = {
            "role": "user",
            "content": f"Passages from my documents:\n\n{context}\n\nQuestion: {question}",
        }
        turn(system, history, None)
    return result


def _agentic(turn: _Turn, system: str, history: list[dict], search_tool, question: str) -> None:
    for step in range(MAX_STEPS):
        last = step == MAX_STEPS - 1
        text, calls, done = turn(system, history, None if last else [SEARCH_TOOL])
        if done.stop != "tool_calls" or not calls:
            return
        history.append(
            {
                "role": "assistant",
                "content": text,
                "tool_calls": [{"id": c.id, "name": c.name, "args": c.args} for c in calls],
                "raw": done.raw,  # resent unchanged by the same adapter (signed thinking etc.)
            }
        )
        for c in calls:
            query = (c.args or {}).get("query")
            if c.name != SEARCH_TOOL.name or not isinstance(query, str) or not query.strip():
                # Malformed or truncated arguments: tell the model instead of guessing.
                content = 'Invalid arguments: call search_documents with {"query": "<text>"}.'
            else:
                content = search_tool(query)
            history.append(
                {"role": "tool", "tool_call_id": c.id, "name": c.name, "content": content}
            )


@dataclass
class _Turn:
    """One streamed model turn, folded into agent.* events and the RunResult."""

    target: provider_services.ChatTarget
    emit: Emit
    result: RunResult
    is_cancelled: Callable[[], bool]
    effort: str

    def __call__(self, system: str, history: list[dict], tools) -> tuple[str, list[ToolCall], Done]:
        text: list[str] = []
        calls: list[ToolCall] = []
        done = Done("end")
        for event in self.target.adapter.stream_chat(
            self.target.model,
            system=system,
            history=history,
            tools=tools,
            effort=self.effort,
            is_cancelled=self.is_cancelled,
        ):
            if isinstance(event, Thinking):
                self.result.thinking += event.text
                self.emit({"type": "agent.thinking", "text": event.text})
            elif isinstance(event, Text):
                text.append(event.text)
                self.result.answer += event.text
                self.emit({"type": "agent.token", "text": event.text})
            elif isinstance(event, ToolCall):
                calls.append(event)
            elif isinstance(event, Done):
                done = event
        if done.stop == "refusal":
            # Reported like any other failure (agent.error) — even if some text already streamed.
            raise ProviderError(REFUSED, permanent=True)
        return "".join(text), calls, done
