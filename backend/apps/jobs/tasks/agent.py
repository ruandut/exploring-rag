"""Demo agent run: streams the same event shapes the real RAG agent will (spec 0005).

Each event is a JSON string published with ctx.aio_put_stream(). The Channels consumer
subscribes to the run's stream and relays each event to the browser.
"""

import asyncio
import json

from hatchet_sdk import Context
from pydantic import BaseModel

from ..hatchet import get_hatchet

hatchet = get_hatchet()


class AgentRunInput(BaseModel):
    user_id: int
    agent_id: str
    message: str


FAKE_CHUNKS = [
    {
        "document": "handbook.pdf",
        "chunk": 12,
        "score": 0.83,
        "text": "Retrieval-augmented generation grounds answers in your own documents.",
    },
    {
        "document": "notes/rag.md",
        "chunk": 3,
        "score": 0.77,
        "text": "Chunks are embedded once at index time and searched by cosine distance.",
    },
]


async def _emit(ctx: Context, event: dict) -> None:
    await ctx.aio_put_stream(json.dumps(event))


async def _stream_words(ctx: Context, kind: str, text: str, delay: float) -> None:
    for word in text.split(" "):
        await _emit(ctx, {"type": kind, "text": word + " "})
        await asyncio.sleep(delay)


@hatchet.task(name="demo-agent", input_validator=AgentRunInput, execution_timeout="5m")
async def demo_agent(input: AgentRunInput, ctx: Context) -> dict:
    # Give the consumer a moment to subscribe: stream chunks published before anyone
    # is listening are not replayed.
    await asyncio.sleep(0.3)

    await _stream_words(
        ctx,
        "agent.thinking",
        f'The user asked: "{input.message}". I should search their documents first, '
        "then answer using only what I find.",
        0.08,
    )

    query = input.message[:80]
    await _emit(
        ctx, {"type": "agent.tool_call", "tool": "search_documents", "args": {"query": query}}
    )
    await asyncio.sleep(0.6)
    await _emit(ctx, {"type": "agent.retrieval", "chunks": FAKE_CHUNKS})

    await _stream_words(
        ctx,
        "agent.token",
        "This is the demo agent, so the answer is canned: in a real run I'd answer from "
        "the retrieved chunks above and cite them like [handbook.pdf#12]. Once spec 0005 "
        "lands, this stream comes from your configured LLM.",
        0.12,
    )
    await _emit(ctx, {"type": "agent.done"})
    return {"ok": True}
