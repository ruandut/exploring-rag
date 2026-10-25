"""Running and scoring one case. Called by the benchmark-case Hatchet task.

case ──▶ target (agent loop, or a bare model) ──▶ answer + retrieved chunks + timings
                                                         │
                              scoring.retrieval (maths) ─┼─ scoring.judge (LLM rubric)
                                                         ▼
                                                scores + explanations
"""

import time

from django.core.exceptions import ObjectDoesNotExist
from openai import OpenAIError

from apps.agents import runner
from apps.agents import services as agent_services
from apps.providers import selectors as provider_selectors
from apps.providers import services as provider_services
from apps.rag import selectors as rag_selectors
from apps.rag.tokens import count_tokens
from apps.scoring import judge, retrieval
from apps.scoring.metrics import CASE_PASS_THRESHOLD, METRICS

from .models import BenchmarkRun, CaseResult

BARE_SYSTEM = "Answer the user's question."


class JudgeFailed(ValueError):
    """The judge's reply couldn't be read. The case fails (retryable) instead of silently
    counting as n/a — a missing score must never let a run pass."""


def execute(result: CaseResult) -> CaseResult:
    """Ask the target, score the answer, and fill in the result (not saved here)."""
    run = result.run
    case = result.case
    started = time.monotonic()
    try:
        answer, retrieved, ttft = _ask_target(run, case["question"])
        result.answer, result.retrieved, result.ttft_ms = answer, retrieved, ttft
        result.tokens = count_tokens(answer)
        result.latency_ms = int((time.monotonic() - started) * 1000)
        scores, explanations = _score(run, case, answer, retrieved, run.owner)
    except (OpenAIError, ValueError, ObjectDoesNotExist) as exc:
        result.status = CaseResult.Status.FAILED
        result.error = (
            provider_services.error_message(exc) if isinstance(exc, OpenAIError) else str(exc)
        )
        result.passed = False
        return result

    result.scores, result.explanations = scores, explanations
    result.status = CaseResult.Status.DONE
    result.passed = all(v is None or v >= CASE_PASS_THRESHOLD for v in scores.values())
    result.error = ""
    return result


def _ask_target(run: BenchmarkRun, question: str) -> tuple[str, list[dict], int | None]:
    started = time.monotonic()
    first_token: list[float] = []

    def mark_first(event: dict) -> None:
        if event.get("type") == "agent.token" and not first_token:
            first_token.append(time.monotonic())

    if run.target_kind == BenchmarkRun.TargetKind.AGENT:
        snap = run.target_snapshot
        agent = agent_services.from_snapshot(run.owner, snap)
        res = runner.run(
            user=run.owner,
            agent=agent,
            messages=[{"role": "user", "content": question}],
            emit=mark_first,
            embedding=_snapshot_embedding(run),
            connection=(
                provider_selectors.get_connection(run.owner, snap["connection"])
                if snap.get("connection")
                else None
            ),
            model=snap.get("model", ""),
        )
        answer, retrieved = res.answer, _dedupe(res.retrieved)
    else:
        snap = run.target_snapshot
        connection = (
            provider_selectors.get_connection(run.owner, snap["connection"])
            if snap.get("connection")
            else None
        )
        target = provider_services.chat_target(
            run.owner, connection=connection, model=snap["model"]
        )
        stream = target.client.chat.completions.create(
            model=target.model,
            messages=[
                {"role": "system", "content": BARE_SYSTEM},
                {"role": "user", "content": question},
            ],
            stream=True,
        )
        parts = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                mark_first({"type": "agent.token"})
                parts.append(chunk.choices[0].delta.content)
        answer, retrieved = "".join(parts), []
    ttft = int((first_token[0] - started) * 1000) if first_token else None
    return answer, retrieved, ttft


def _snapshot_embedding(run: BenchmarkRun):
    """The embedding the run searches. A deleted one fails the case (retryable after you pick
    another) rather than quietly searching something else. Runs from before spec 0010 have no
    embedding in their snapshot: they searched everything, i.e. the oldest embedding now."""
    snap = run.target_snapshot
    if "embedding" not in snap:
        return rag_selectors.default_embedding(run.owner)
    if snap["embedding"] is None:
        return None
    found = rag_selectors.embeddings_for(run.owner).filter(pk=snap["embedding"]["id"]).first()
    if found is None:
        raise ValueError(f"The embedding “{snap['embedding']['name']}” was deleted")
    return found


def _dedupe(retrieved: list[dict]) -> list[dict]:
    """Agents may search several times; keep each chunk once, in first-retrieved order."""
    seen, out = set(), []
    for c in retrieved:
        key = (c["document"], c["chunk"])
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _judge_target(run: BenchmarkRun, owner) -> provider_services.ChatTarget:
    suite = run.suite_snapshot
    connection = (
        provider_selectors.get_connection(owner, suite["judge_connection"])
        if suite.get("judge_connection")
        else None
    )
    return provider_services.chat_target(
        owner, connection=connection, model=suite.get("judge_model", "")
    )


def _score(run: BenchmarkRun, case: dict, answer: str, retrieved: list[dict], owner):
    suite = run.suite_snapshot
    k = suite["k"]
    scores: dict[str, float | None] = {}
    explanations: dict[str, str] = {}
    metric_ids = ["refusal_rate"] if case["kind"] == "refusal" else suite["metrics"]
    judge_target = None
    items = [retrieval.Item(c["document"], c["text"]) for c in retrieved]
    gold = retrieval.Gold(case.get("relevant_documents", []), case.get("evidence", ""))

    for metric_id in metric_ids:
        metric = METRICS[metric_id]
        if metric.kind == "retrieval":
            if run.target_kind == BenchmarkRun.TargetKind.MODEL:
                scores[metric_id], explanations[metric_id] = (
                    None,
                    "n/a — a bare model retrieves nothing",
                )
            elif not gold.documents:
                scores[metric_id], explanations[metric_id] = (
                    None,
                    "n/a — the case names no relevant document",
                )
            else:
                value, why = retrieval.score(metric_id, items, gold, k)
                scores[metric_id], explanations[metric_id] = round(value, 4), why
        elif metric.kind == "judge":
            judge_target = judge_target or _judge_target(run, owner)
            verdict = judge.judge(
                judge_target.client,
                judge_target.model,
                metric_id,
                question=case["question"],
                answer=answer,
                contexts=[c["text"] for c in retrieved],
                reference=case.get("reference_answer", ""),
            )
            if verdict.score is None:
                raise JudgeFailed(
                    f"Judge ({judge_target.label}) on {metric_id}: {verdict.reasoning}"
                )
            scores[metric_id], explanations[metric_id] = verdict.score, verdict.reasoning
    return scores, explanations
