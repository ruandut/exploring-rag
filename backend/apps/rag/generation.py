"""Generation strategies: how retrieved chunks are turned into material for the answer.

The agent calls the `search_documents` tool; what the tool hands back depends on the strategy:
- stuff       the raw chunks; the model may answer freely.
- cited       the raw chunks, and the system prompt requires [document#chunk] citations.
- map_reduce  map: the LLM extracts what each chunk says about the question (in parallel in
              spirit, sequential here); reduce: the agent writes the answer from those notes.
- refine      the LLM drafts an answer from the first chunk, then refines it chunk by chunk.
- corrective  the LLM grades each chunk's relevance; if none pass, the query is rewritten and
              searched once more (a lightweight "corrective RAG").
"""

from collections.abc import Callable

from .llm import Completer
from .retrieval import Retrieved

STRATEGIES = ("stuff", "cited", "map_reduce", "refine", "corrective")


def system_instructions(strategy: str) -> str:
    base = (
        "You answer questions using the user's documents. Call the search_documents tool to "
        "find relevant passages before answering; search again with a different query if the "
        "results don't help. If the documents don't contain the answer, say you don't know — "
        "never invent facts."
    )
    if strategy == "stuff":
        return base
    return base + (
        " Cite every fact with the source tag exactly as shown in the search results, e.g. "
        "[handbook.md#3]. Only cite tags that appeared in the results."
    )


def format_chunks(chunks: list[Retrieved]) -> str:
    if not chunks:
        return "No matching passages were found."
    # parent_text (parent-document strategy) gives the model the bigger surrounding context.
    return "\n\n".join(f"[{c.tag}]\n{c.parent_text or c.text}" for c in chunks)


def tool_result(
    strategy: str,
    question: str,
    chunks: list[Retrieved],
    *,
    llm: Completer,
    research: Callable[[str], list[Retrieved]],
) -> tuple[str, list[Retrieved]]:
    """Returns (text for the tool message, chunks actually used)."""
    if strategy == "map_reduce" and chunks:
        notes = []
        for c in chunks:
            note = llm.complete(
                f"Question: {question}\n\nPassage [{c.tag}]:\n{c.text}\n\nWhat does this passage "
                "say that helps answer the question? Reply in one or two sentences, or NONE.",
            )
            if note.strip().upper() != "NONE":
                notes.append(f"[{c.tag}] {note}")
        return (
            "Notes from each passage:\n" + "\n".join(notes)
        ) if notes else "No passage was relevant.", chunks

    if strategy == "refine" and chunks:
        draft = ""
        for c in chunks:
            draft = llm.complete(
                f"Question: {question}\n\nCurrent draft answer:\n{draft or '(none yet)'}\n\n"
                f"New passage [{c.tag}]:\n{c.text}\n\n"
                "Improve the draft using the new passage if it helps; keep [document#chunk] "
                "citations. Reply with the draft only.",
                max_tokens=500,
            )
        return f"Draft answer refined over {len(chunks)} passages:\n{draft}", chunks

    if strategy == "corrective":
        relevant = [c for c in chunks if _is_relevant(llm, question, c)]
        if not relevant:
            rewritten = llm.complete(
                "The search for this question found nothing useful. "
                f"Write a better search query.\n\n{question}",
            )
            relevant = research(rewritten)
        return format_chunks(relevant), relevant

    return format_chunks(chunks), chunks


def _is_relevant(llm: Completer, question: str, chunk: Retrieved) -> bool:
    reply = llm.complete(
        f"Question: {question}\n\nPassage:\n{chunk.text}\n\nDoes the passage help answer the "
        "question? Reply yes or no.",
        max_tokens=3,
    )
    return reply.strip().lower().startswith(("yes", "ok"))
