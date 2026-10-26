"""LLM-as-judge: one call per metric per case, with a fixed rubric (at temperature 0 where the
provider allows it — current Claude models reject sampling parameters, so the rubric does the
work).

Simpler than RAGAS (which splits answers into claims and checks each one): a single rubric
call returning JSON {"score": 0..1, "reasoning": "..."}. Cheaper — fine for local judges —
but coarser. The reasoning is stored so every score can be audited.
"""

import json
import re
from dataclasses import dataclass

RUBRICS = {
    "faithfulness": "Is every claim in the ANSWER supported by the CONTEXT? 1 = fully supported, "
    "0 = mostly unsupported or contradicted. An answer that says it doesn't know is faithful.",
    "answer_relevancy": "Does the ANSWER directly address the QUESTION? 1 = fully on point, "
    "0 = off topic or evasive.",
    "answer_correctness": "Does the ANSWER state the same facts as the REFERENCE answer? "
    "1 = same facts, 0 = wrong or missing.",
    "context_precision": "How much of the CONTEXT is relevant to the QUESTION, with relevant "
    "passages ranked first? 1 = all relevant, 0 = none.",
    "context_recall": "Does the CONTEXT contain everything needed to give the REFERENCE answer? "
    "1 = everything, 0 = nothing.",
    "citation_accuracy": "Do the [document#chunk] citations in the ANSWER point to CONTEXT "
    "passages that support the cited sentences? 1 = all correct, 0 = wrong or missing citations.",
    "refusal_rate": "The QUESTION cannot be answered from the user's documents. Did the ANSWER "
    "say it doesn't know (1) rather than inventing an answer (0)?",
}


@dataclass
class Verdict:
    score: float | None
    reasoning: str


def build_prompt(
    metric_id: str, *, question: str, answer: str, contexts: list[str], reference: str
) -> str:
    context = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts)) or "(none)"
    return (
        "You are grading one answer from a retrieval-augmented assistant.\n"
        f"Metric: {metric_id}\nRubric: {RUBRICS[metric_id]}\n\n"
        f"QUESTION:\n{question}\n\nANSWER:\n{answer or '(empty)'}\n\n"
        f"CONTEXT:\n{context}\n\nREFERENCE:\n{reference or '(none)'}\n\n"
        'Reply with JSON only: {"score": <number from 0 to 1>, "reasoning": "<one sentence>"}'
    )


def parse(reply: str) -> Verdict:
    match = re.search(r"\{.*\}", reply, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            value = float(data["score"])
            return Verdict(min(max(value, 0.0), 1.0), str(data.get("reasoning", "")))
        except ValueError, KeyError, TypeError:
            pass
    # A reply cut off mid-JSON (common when a reasoning model runs out of tokens) usually
    # still contains the score.
    salvage = re.search(r'"score"\s*:\s*(-?\d+(?:\.\d+)?)', reply)
    if salvage:
        value = min(max(float(salvage.group(1)), 0.0), 1.0)
        return Verdict(value, "(the judge's reply was cut off; score recovered)")
    if not reply.strip():
        return Verdict(
            None,
            "The judge returned an empty reply (a reasoning model may have spent its whole "
            "token budget thinking).",
        )
    return Verdict(None, f"The judge's reply wasn't valid JSON: {reply[:200]}")


def judge(llm, metric_id: str, **fields) -> Verdict:
    """llm: anything with complete(prompt, max_tokens) — a providers ChatTarget, so the judge
    runs on whichever provider and model the suite chose."""
    # Generous: reasoning models (e.g. Gemma, DeepSeek-R1, Claude) spend part of this thinking.
    return parse(llm.complete(build_prompt(metric_id, **fields), max_tokens=2000))
