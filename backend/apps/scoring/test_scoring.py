"""Metric maths, judge parsing and boundaries — pure functions, no database."""

import math

import pytest

from apps.scoring import aggregate, judge, retrieval
from apps.scoring.metrics import METRICS, SELECTABLE, display_name

I = retrieval.Item  # noqa: E741


def ranked(*docs):
    return [I(d, f"text of {d}") for d in docs]


# The examples from the original AT-0006-02, checked by hand.
@pytest.mark.parametrize(
    ("metric", "k", "expected"),
    [("hit_rate", 3, 1.0), ("recall", 3, 0.5), ("precision", 5, 0.4), ("mrr", 5, 0.5)],
)
def test_hand_checked_examples(metric, k, expected):
    gold = retrieval.Gold(["b", "e"])
    value, _ = retrieval.score(metric, ranked("a", "b", "c", "d", "e"), gold, k)
    assert value == pytest.approx(expected)


def test_recall_counts_documents_not_chunks():
    gold = retrieval.Gold(["handbook.md"])
    value, why = retrieval.recall(ranked("handbook.md", "handbook.md", "x"), gold, 5)
    assert value == 1.0
    assert why == "1 of 1 relevant documents retrieved (top 5)"


def test_evidence_must_be_in_the_chunk():
    gold = retrieval.Gold(["handbook.md"], evidence="refund window is 30")
    hit = [I("handbook.md", "The Refund   window is 30 days.")]  # case and spacing don't matter
    miss = [I("handbook.md", "Leave: 25 days.")]
    assert retrieval.hit_rate(hit, gold, 5)[0] == 1.0
    assert retrieval.hit_rate(miss, gold, 5)[0] == 0.0


def test_ndcg_rewards_relevant_chunks_ranked_first():
    gold = retrieval.Gold(["good"])
    best, _ = retrieval.ndcg(ranked("good", "bad", "bad"), gold, 3)
    worse, _ = retrieval.ndcg(ranked("bad", "bad", "good"), gold, 3)
    assert best == 1.0
    assert worse == pytest.approx(1 / math.log2(4))


def test_nothing_relevant_scores_zero():
    gold = retrieval.Gold(["x"])
    for metric in retrieval.FUNCTIONS:
        assert retrieval.score(metric, ranked("a", "b"), gold, 5)[0] == 0.0


def test_judge_reply_parsing():
    assert judge.parse('{"score": 0.8, "reasoning": "mostly supported"}') == judge.Verdict(
        0.8, "mostly supported"
    )
    assert judge.parse('Sure! ```json\n{"score": 1.5}\n```').score == 1.0  # clamped
    bad = judge.parse("I think it's good")
    assert bad.score is None and "wasn't valid JSON" in bad.reasoning


def test_truncated_judge_replies_still_yield_the_score():
    cut = '```json\n{\n  "score": 1,\n  "reasoning": "The answer states the core fact (Paris)'
    assert judge.parse(cut).score == 1.0


def test_empty_judge_replies_explain_why():
    verdict = judge.parse("")
    assert verdict.score is None and "token budget" in verdict.reasoning


def test_judge_prompt_contains_rubric_and_inputs():
    prompt = judge.build_prompt(
        "faithfulness", question="Q?", answer="A.", contexts=["c1"], reference="R"
    )
    assert "Metric: faithfulness" in prompt and "[0] c1" in prompt and "REFERENCE:\nR" in prompt


def test_every_judge_metric_has_a_rubric():
    assert {m.id for m in METRICS.values() if m.kind == "judge"} == set(judge.RUBRICS)


def test_selectable_metrics_and_names():
    assert "refusal_rate" not in SELECTABLE and "recall" in SELECTABLE
    assert display_name("recall", 5) == "Recall@5"
    assert display_name("mrr", 5) == "MRR"


def test_aggregates():
    stats = aggregate.summarise([0.2, 0.4, 0.6, 0.8, 1.0])
    assert stats == {"mean": pytest.approx(0.6), "p50": 0.6, "p95": 1.0, "n": 5}
    assert aggregate.summarise([])["mean"] is None


def test_boundary_margins():
    fail = aggregate.check("faithfulness", "mean", "gte", 0.9, {"mean": 0.8})
    assert (fail.passed, fail.margin) == (False, -0.1)
    ok = aggregate.check("latency_total", "p95", "lte", 8, {"p95": 3.5})
    assert (ok.passed, ok.margin) == (True, 4.5)


def test_boundaries_on_missing_metrics_are_skipped():
    skipped = aggregate.check("recall", "mean", "gte", 0.8, {"mean": None})
    assert skipped.passed is None and skipped.actual is None
