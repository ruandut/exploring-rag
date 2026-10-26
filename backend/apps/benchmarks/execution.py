"""Running and scoring one case. Called by the benchmark-case Hatchet task.

case ──▶ target (agent loop, or a bare model) ──▶ answer + retrieved chunks + timings
                                                         │
                              scoring.retrieval (maths) ─┼─ scoring.judge (LLM rubric)
                                                         ▼
                                                scores + explanations

Timings (spec 0011) come from the agent.* events the run already emits, so the agent loop
doesn't know it's being timed. Every moment belongs to the phase of the latest event:

    question sent ─ waiting ─▶ tool_call ─ searching ─▶ retrieval ─ waiting ─▶ thinking
      ─ reasoning ─▶ token ─ writing ─▶ end

"Waiting" is network + the model reading its prompt, before it outputs anything.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from django.core.exceptions import ObjectDoesNotExist

from apps.agents import runner
from apps.agents import services as agent_services
from apps.providers import selectors as provider_selectors
from apps.providers import services as provider_services
from apps.providers.llm import ProviderError, Text, Thinking
from apps.rag import selectors as rag_selectors
from apps.rag.tokens import count_tokens
from apps.scoring import judge, retrieval
from apps.scoring.metrics import CASE_PASS_THRESHOLD, METRICS

from .models import BenchmarkRun, CaseResult

BARE_SYSTEM = "Answer the user's question."


# Which phase an agent.* event starts. Anything else (e.g. agent.started) changes nothing.
PHASE_OF = {
    "agent.tool_call": "search",
    "agent.retrieval": "waiting",  # results are in; the model now reads them
    "agent.thinking": "reasoning",
    "agent.token": "writing",
}
PHASES = ("waiting", "search", "reasoning", "writing")


def _now() -> float:
    """Monotonic seconds; a function so tests can drive the clock."""
    return time.monotonic()


@dataclass
class PhaseClock:
    """Splits one answer's wall time into phases. Times are monotonic seconds."""

    started: float = field(default_factory=lambda: _now())
    marks: list[tuple[str, float]] = field(default_factory=list)  # (phase, when it began)
    first_token: float | None = None
    ended: float | None = None

    def event(self, event_type: str) -> None:
        phase = PHASE_OF.get(event_type)
        if phase is None:
            return
        now = _now()
        if phase == "writing" and self.first_token is None:
            self.first_token = now
        if not self.marks or self.marks[-1][0] != phase:
            self.marks.append((phase, now))

    def stop(self) -> None:
        self.ended = _now()

    def ms(self, t: float) -> int:
        return int(round((t - self.started) * 1000))

    def phases_ms(self) -> dict[str, int]:
        """Milliseconds per phase. Boundaries are rounded once, before subtracting, so the
        phases add up to the total exactly instead of drifting by rounding errors."""
        assert self.ended is not None
        totals = dict.fromkeys(PHASES, 0)
        spans = [("waiting", self.started), *self.marks, ("", self.ended)]
        for (phase, begin), (_, end) in zip(spans, spans[1:], strict=False):
            totals[phase] += self.ms(end) - self.ms(begin)
        return totals


class JudgeFailed(ValueError):
    """The judge's reply couldn't be read. The case fails (retryable) instead of silently
    counting as n/a — a missing score must never let a run pass."""


def execute(result: CaseResult, is_cancelled: Callable[[], bool] = lambda: False) -> CaseResult:
    """Ask the target, score the answer, and fill in the result (not saved here).

    `is_cancelled` is polled while the target streams; once it's true the agent loop or
    adapter raises `Cancelled` (spec 0012), which propagates — a stopped case has no result."""
    run = result.run
    case = result.case
    try:
        clock = PhaseClock()
        answer, retrieved = _ask_target(run, case["question"], clock, is_cancelled)
        clock.stop()
        result.answer, result.retrieved = answer, retrieved
        result.tokens = count_tokens(answer)
        _record_timings(result, clock, searches=run.target_kind == BenchmarkRun.TargetKind.AGENT)
        judging = _now()
        scores, explanations = _score(run, case, answer, retrieved, run.owner)
        result.judge_ms = int(round((_now() - judging) * 1000))
    except (ProviderError, ValueError, ObjectDoesNotExist) as exc:
        result.status = CaseResult.Status.FAILED
        result.error = str(exc)
        result.passed = False
        return result

    result.scores, result.explanations = scores, explanations
    result.status = CaseResult.Status.DONE
    result.passed = all(v is None or v >= CASE_PASS_THRESHOLD for v in scores.values())
    result.error = ""
    return result


def _record_timings(result: CaseResult, clock: PhaseClock, *, searches: bool) -> None:
    phases = clock.phases_ms()
    result.latency_ms = clock.ms(clock.ended)
    result.ttft_ms = clock.ms(clock.first_token) if clock.first_token is not None else None
    result.waiting_ms = phases["waiting"]
    result.search_ms = phases["search"] if searches else None  # a bare model can't search
    result.reasoning_ms = phases["reasoning"]
    result.writing_ms = phases["writing"]
    # No writing time (an empty answer) has no speed — n/a, never 0 or infinity.
    result.tokens_per_second = (
        round(result.tokens / (phases["writing"] / 1000), 2) if phases["writing"] else None
    )


def _ask_target(
    run: BenchmarkRun, question: str, clock: PhaseClock, is_cancelled: Callable[[], bool]
) -> tuple[str, list[dict]]:
    if run.target_kind == BenchmarkRun.TargetKind.AGENT:
        snap = run.target_snapshot
        agent = agent_services.from_snapshot(run.owner, snap)
        res = runner.run(
            user=run.owner,
            agent=agent,
            messages=[{"role": "user", "content": question}],
            emit=lambda event: clock.event(event.get("type", "")),
            is_cancelled=is_cancelled,
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
        parts = []
        for event in target.adapter.stream_chat(
            target.model,
            system=BARE_SYSTEM,
            history=[{"role": "user", "content": question}],
            is_cancelled=is_cancelled,
        ):
            if isinstance(event, Thinking):
                clock.event("agent.thinking")
            elif isinstance(event, Text):
                clock.event("agent.token")
                parts.append(event.text)
        answer, retrieved = "".join(parts), []
    return answer, retrieved


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
                judge_target,
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
