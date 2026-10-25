"""The agent loop: an LLM that decides when to search the user's documents.

    messages ──▶ LLM (with the search_documents tool) ──▶ wants a search? ──yes──▶ retrieve,
        ▲                                                       │               add results
        └───────────────────────────────────────────────────────┘                    │
                                                                no ──▶ streamed answer ◀┘

Every step is reported through `emit` (agent.thinking / tool_call / retrieval / token), which the
Hatchet task turns into stream chunks for the browser.

Models that can't call tools (many small local models) fall back to classic "retrieve then
answer" RAG: search once with the question, put the results in the prompt, stream the answer.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from openai import BadRequestError, OpenAI

from apps.providers import services as provider_services
from apps.rag import generation, retrieval
from apps.rag import selectors as rag_selectors
from apps.rag.embedding import make_embedder
from apps.rag.models import EmbeddingIndex

from .models import Agent

MAX_STEPS = 4  # tool rounds before the model must answer

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the user's documents for passages relevant to a query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for — a question or keywords.",
                }
            },
            "required": ["query"],
        },
    },
}

Emit = Callable[[dict], None]


class Cancelled(Exception):
    pass


@dataclass
class RunResult:
    answer: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    model: str = ""
    mode: str = "agentic"  # or "pipeline" when the model can't call tools


def run(
    *,
    user,
    agent: Agent,
    messages: list[dict],
    emit: Emit,
    is_cancelled: Callable[[], bool] = lambda: False,
    folder_ids: list[int] | None = None,
    embedding: EmbeddingIndex | None = None,
) -> RunResult:
    """folder_ids overrides agent.folders — used for unsaved agents rebuilt from a snapshot.
    embedding is what gets searched; the user's oldest embedding when not given."""
    target = provider_services.chat_target(user, connection=agent.connection, model=agent.model)
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
    if folder_ids is None:
        folder_ids = list(agent.folders.values_list("pk", flat=True))
    folder_ids = folder_ids or None  # none = all documents

    # The query is embedded by the embedding's own model and endpoint — vectors are only
    # comparable with vectors from the same model — whichever model writes the answer.
    embedding = embedding or rag_selectors.default_embedding(user)
    embed = (
        make_embedder(
            provider_services.embedding_client(user, embedding.connection), embedding.model
        )
        if embedding
        else None
    )

    def do_search(query: str) -> list[retrieval.Retrieved]:
        if embed is None:
            return []
        return retrieval.search(
            user,
            query,
            config=search_cfg,
            index=embedding,
            folder_ids=folder_ids,
            embed=embed,
            client=target.client,
            chat_model=target.model,
        )

    def search_tool(query: str) -> str:
        result.tool_calls.append({"tool": "search_documents", "args": {"query": query}})
        emit({"type": "agent.tool_call", "tool": "search_documents", "args": {"query": query}})
        if embed is None:
            text, used = "Document search is unavailable: no embedding is selected.", []
        else:
            text, used = generation.tool_result(
                strategy,
                question,
                do_search(query),
                client=target.client,
                model=target.model,
                research=do_search,
            )
        events = [c.as_event() for c in used]
        result.retrieved.extend(events)
        emit({"type": "agent.retrieval", "chunks": events})
        return text

    system = "\n\n".join(
        p for p in (agent.system_message.strip(), generation.system_instructions(strategy)) if p
    )
    convo: list[dict] = [{"role": "system", "content": system}, *messages]

    try:
        _agentic(target.client, target.model, convo, search_tool, emit, result, is_cancelled)
    except BadRequestError as exc:
        if "tool" not in provider_services.error_message(exc).lower():
            raise
        result.mode = "pipeline"
        note = "This model can't call tools, so I searched once with your question.\n"
        result.thinking += note
        emit({"type": "agent.thinking", "text": note})
        context = search_tool(question)
        convo[-1] = {
            "role": "user",
            "content": f"Passages from my documents:\n\n{context}\n\nQuestion: {question}",
        }
        _stream(target.client, target.model, convo, None, emit, result, is_cancelled)
    return result


def _agentic(client, model, convo, search_tool, emit, result, is_cancelled) -> None:
    for step in range(MAX_STEPS):
        last = step == MAX_STEPS - 1
        content, calls = _stream(
            client, model, convo, None if last else [SEARCH_TOOL], emit, result, is_cancelled
        )
        if not calls:
            return
        convo.append(
            {
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in calls
                ],
            }
        )
        for c in calls:
            try:
                query = json.loads(c["arguments"] or "{}").get("query", "")
            except json.JSONDecodeError:
                query = ""
            text = search_tool(query or convo[1 if len(convo) > 1 else 0]["content"])
            convo.append({"role": "tool", "tool_call_id": c["id"], "content": text})


def _stream(
    client: OpenAI, model, convo, tools, emit, result: RunResult, is_cancelled
) -> tuple[str, list[dict]]:
    """One streamed completion. Emits tokens / reasoning as they arrive; returns the text and
    any tool calls (whose names and JSON arguments arrive in fragments)."""
    kwargs = {"model": model, "messages": convo, "stream": True}
    if tools:
        kwargs["tools"] = tools
    stream = client.chat.completions.create(**kwargs)
    text: list[str] = []
    calls: dict[int, dict] = {}
    try:
        for chunk in stream:
            if is_cancelled():
                raise Cancelled
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            # Reasoning isn't in the OpenAI schema; DeepSeek / OpenRouter / Ollama add it as an
            # extra field (reasoning_content or reasoning).
            extra = delta.model_extra or {}
            reasoning = extra.get("reasoning_content") or extra.get("reasoning")
            if reasoning:
                result.thinking += reasoning
                emit({"type": "agent.thinking", "text": reasoning})
            if delta.content:
                text.append(delta.content)
                result.answer += delta.content
                emit({"type": "agent.token", "text": delta.content})
            for tc in delta.tool_calls or []:
                slot = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                slot["id"] = tc.id or slot["id"] or f"call_{tc.index}"
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments
    finally:
        stream.close()
    return "".join(text), [calls[i] for i in sorted(calls)]
