"""Starting runs, executing cases (with fakes) and summarising — no Hatchet, no network."""

from types import SimpleNamespace

import pytest
from openai import APIConnectionError
from rest_framework.test import APIClient

from apps.agents.models import Agent
from apps.agents.runner import RunResult
from apps.benchmarks import execution, services
from apps.benchmarks.models import BenchmarkRun, CaseResult
from apps.evals import services as eval_services
from apps.providers.models import ProviderConfig
from apps.scoring import judge as judge_module

CASES = [
    {
        "kind": "qa",
        "question": "What is the refund window?",
        "reference_answer": "30 days",
        "relevant_documents": ["handbook.md"],
        "evidence": "refund window is 30",
    },
    {"kind": "refusal", "question": "Who won the 2030 World Cup?"},
]


@pytest.fixture(autouse=True)
def no_hatchet(monkeypatch):
    launched = []
    monkeypatch.setattr(services, "_launch", lambda run, ids: launched.append((run.pk, ids)))
    monkeypatch.setattr(services, "send_to_user", lambda *a: None)
    return launched


@pytest.fixture
def setup(user):
    ProviderConfig.objects.create(owner=user, base_url="http://fake/v1", chat_model="fake-chat")
    agent = Agent.objects.create(owner=user, name="Docs helper", system_message="Original")
    suite = eval_services.save_suite(
        user,
        data={
            "name": "Basics",
            "metrics": ["faithfulness", "recall"],
            "cases": CASES,
            "boundaries": [
                {"metric": "faithfulness", "aggregate": "mean", "comparator": "gte", "value": 0.9},
                {"metric": "recall", "aggregate": "mean", "comparator": "gte", "value": 0.5},
            ],
        },
    )
    return SimpleNamespace(agent=agent, suite=suite)


def fake_agent(monkeypatch, answer="The refund window is 30 days [handbook.md#0].", error=None):
    def run(**kwargs):
        if error:
            raise error
        kwargs["emit"]({"type": "agent.token", "text": answer})
        return RunResult(
            answer=answer,
            retrieved=[
                {
                    "document": "handbook.md",
                    "chunk": 0,
                    "score": 0.9,
                    "text": "The refund window is 30 days.",
                },
                {
                    "document": "handbook.md",
                    "chunk": 0,
                    "score": 0.9,
                    "text": "The refund window is 30 days.",
                },
            ],
        )

    monkeypatch.setattr(execution.runner, "run", run)


def fake_judge(monkeypatch, score=1.0):
    seen = []

    def judge(client, model, metric_id, **fields):
        seen.append((model, metric_id))
        value = 0.0 if metric_id == "refusal_rate" and "Brazil" in fields["answer"] else score
        return judge_module.Verdict(value, f"{metric_id} looks {value}")

    monkeypatch.setattr(execution.judge, "judge", judge)
    monkeypatch.setattr("apps.providers.services.client_for", lambda user: SimpleNamespace())
    return seen


def run_all(run):
    for result in run.results.all():
        execution.execute(result)
        result.save()
    return services.finalize(run)


def test_start_runs_snapshots_and_creates_pending_results(db, user, setup, no_hatchet):
    [run] = services.start_runs(user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk}])
    # No embedding yet, so the oldest one ("left out" = the default) is none at all.
    assert run.target_label == "Docs helper · no embedding"
    assert run.target_snapshot["system_message"] == "Original"
    assert run.suite_snapshot["version"] == 1
    assert run.results.filter(status="pending").count() == 2


def test_at_0010_17_two_embeddings_compare_on_the_same_agent(db, user, setup, no_hatchet):
    from apps.rag.models import EmbeddingIndex

    small = EmbeddingIndex.objects.create(
        owner=user, name="Small", model="fake-embed", dimensions=8, all_documents=True
    )
    wide = EmbeddingIndex.objects.create(
        owner=user, name="Wide", model="fake-embed-16", dimensions=16, all_documents=True
    )
    runs = services.start_runs(
        user,
        setup.suite,
        [
            {"kind": "agent", "agent": setup.agent.pk, "embedding": small.pk},
            {"kind": "agent", "agent": setup.agent.pk, "embedding": wide.pk, "model": "m2"},
        ],
    )
    assert [r.target_label for r in runs] == ["Docs helper · Small", "Docs helper · Wide"]
    assert runs[1].target_snapshot["embedding"] == {
        "id": wide.pk,
        "name": "Wide",
        "model": "fake-embed-16",
        "dimensions": 16,
        "strategy": "recursive",
        "chunk_size": 512,
        "chunk_overlap": 64,
    }
    assert runs[1].target_snapshot["model"] == "m2"
    # Deleting the embedding later never changes what the run says it used.
    wide.delete()
    runs[1].refresh_from_db()
    assert runs[1].target_snapshot["embedding"]["name"] == "Wide"


def test_a_deleted_embedding_fails_the_case(db, user, setup, no_hatchet):
    from apps.benchmarks import execution
    from apps.rag.models import EmbeddingIndex

    small = EmbeddingIndex.objects.create(owner=user, name="Small", model="m", all_documents=True)
    [run] = services.start_runs(
        user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk, "embedding": small.pk}]
    )
    small.delete()
    result = execution.execute(run.results.first())
    assert result.status == "failed" and "was deleted" in result.error


def test_two_targets_share_a_compare_group(db, user, setup):
    runs = services.start_runs(
        user,
        setup.suite,
        [
            {"kind": "model", "connection": None, "model": "fake-chat"},
            {"kind": "agent", "agent": setup.agent.pk},
        ],
    )
    assert runs[0].compare_group == runs[1].compare_group is not None
    assert runs[0].target_label == "Default provider · fake-chat (bare)"


def test_a_passing_run(db, user, setup, monkeypatch):
    fake_agent(monkeypatch)
    fake_judge(monkeypatch)
    [run] = services.start_runs(user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk}])
    run = run_all(run)
    qa = run.results.get(position=0)
    assert qa.scores == {"faithfulness": 1.0, "recall": 1.0}
    assert qa.explanations["recall"] == "1 of 1 relevant documents retrieved (top 5)"
    assert len(qa.retrieved) == 1  # duplicate chunk from a second search removed
    assert qa.latency_ms is not None and qa.ttft_ms is not None and qa.tokens > 0
    refusal = run.results.get(position=1)
    assert list(refusal.scores) == ["refusal_rate"]
    assert run.status == "passed"
    assert run.summary["metrics"]["faithfulness"]["mean"] == 1.0
    assert all(b["passed"] for b in run.summary["boundaries"])


def test_a_boundary_fails_with_its_margin(db, user, setup, monkeypatch):
    fake_agent(monkeypatch)
    fake_judge(monkeypatch, score=0.8)
    [run] = services.start_runs(user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk}])
    run = run_all(run)
    faithful = next(b for b in run.summary["boundaries"] if b["metric"] == "faithfulness")
    assert (faithful["passed"], faithful["margin"]) == (False, -0.1)
    assert run.status == "failed"


def test_bare_models_get_na_retrieval_and_skipped_boundaries(db, user, setup, monkeypatch):
    fake_judge(monkeypatch)

    class Stream:
        def __init__(self, text):
            self.chunks = [
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=w))])
                for w in text.split(" ")
            ]

        def __iter__(self):
            return iter(self.chunks)

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **k: Stream("It was Brazil"))
        )
    )
    monkeypatch.setattr("apps.providers.services.build_client", lambda *a, **k: client)
    monkeypatch.setattr("apps.providers.services.client_for", lambda user: client)
    [run] = services.start_runs(
        user, setup.suite, [{"kind": "model", "connection": None, "model": "fake-chat"}]
    )
    run = run_all(run)
    qa = run.results.get(position=0)
    assert qa.scores["recall"] is None and qa.explanations["recall"].startswith("n/a")
    recall = next(b for b in run.summary["boundaries"] if b["metric"] == "recall")
    assert recall["passed"] is None  # skipped, not failed
    assert run.results.get(position=1).passed is False  # it invented an answer


def test_unreachable_provider_fails_cases_and_retry_reruns_them(
    db, user, setup, monkeypatch, no_hatchet, django_capture_on_commit_callbacks
):
    fake_agent(monkeypatch, error=APIConnectionError(request=SimpleNamespace()))
    fake_judge(monkeypatch)
    [run] = services.start_runs(user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk}])
    run = run_all(run)
    assert run.summary["failed_cases"] == 2 and run.status == "failed"
    assert "Connection error" in run.results.first().error

    no_hatchet.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert services.retry_failed(run) == 2
    assert no_hatchet and len(no_hatchet[0][1]) == 2
    fake_agent(monkeypatch)
    run = run_all(BenchmarkRun.objects.get(pk=run.pk))
    assert run.summary["failed_cases"] == 0 and run.status == "passed"


def test_editing_the_agent_does_not_change_the_run(db, user, setup):
    [run] = services.start_runs(user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk}])
    setup.agent.system_message = "Something else"
    setup.agent.save()
    run.refresh_from_db()
    assert run.target_snapshot["system_message"] == "Original"


def test_runs_api_is_private(db, user, other_user, setup, auth_api):
    res = auth_api.post(
        "/api/benchmarks/runs/",
        {"suite": setup.suite.pk, "targets": [{"kind": "agent", "agent": setup.agent.pk}]},
        format="json",
    )
    assert res.status_code == 201, res.content
    run_id = res.json()[0]["id"]
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get(f"/api/benchmarks/runs/{run_id}/").status_code == 404
    res = bob.post(
        "/api/benchmarks/runs/",
        {"suite": setup.suite.pk, "targets": [{"kind": "model", "model": "x"}]},
        format="json",
    )
    assert res.status_code == 404
    assert CaseResult.objects.count() == 2


def test_an_unreadable_judge_reply_fails_the_case(db, user, setup, monkeypatch):
    fake_agent(monkeypatch)
    monkeypatch.setattr(
        execution.judge, "judge", lambda *a, **k: judge_module.Verdict(None, "empty reply")
    )
    monkeypatch.setattr("apps.providers.services.client_for", lambda user: SimpleNamespace())
    [run] = services.start_runs(user, setup.suite, [{"kind": "agent", "agent": setup.agent.pk}])
    run = run_all(run)
    first = run.results.get(position=0)
    assert first.status == "failed" and "empty reply" in first.error
    assert run.status == "failed"  # a missing score never lets a run pass
