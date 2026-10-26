"""Stopping a running benchmark run (spec 0012) — no Hatchet, no network."""

from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.benchmarks import execution, services, tasks
from apps.benchmarks.models import BenchmarkRun, CaseResult
from apps.evals import services as eval_services
from apps.providers.llm import Cancelled
from apps.providers.llm.testing import Done, FakeAdapter, Text
from apps.providers.models import ProviderConfig

CASES = [
    {"kind": "refusal", "question": "Who won the 2030 World Cup?"},
    {"kind": "refusal", "question": "Who won the 2034 World Cup?"},
    {"kind": "refusal", "question": "Who won the 2038 World Cup?"},
]


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    sent, cancelled = [], []
    monkeypatch.setattr(services, "_launch", lambda run, ids: None)
    monkeypatch.setattr(services, "send_to_user", lambda user_id, payload: sent.append(payload))
    monkeypatch.setattr(services, "_cancel_in_hatchet", cancelled.append)
    return SimpleNamespace(sent=sent, cancelled=cancelled)


@pytest.fixture
def run(user):
    ProviderConfig.objects.create(owner=user, base_url="http://fake/v1", chat_model="fake-chat")
    suite = eval_services.save_suite(
        user,
        data={
            "name": "Slow",
            "metrics": [],
            "cases": CASES,
            "boundaries": [
                {"metric": "error_rate", "aggregate": "mean", "comparator": "lte", "value": 0.5}
            ],
        },
    )
    [run] = services.start_runs(user, suite, [{"kind": "model", "model": "fake-chat"}])
    run.hatchet_run_id = "hatchet-123"
    run.save()
    # The first case finished before Stop was pressed; the other two are still pending.
    first = run.results.get(position=0)
    first.status, first.passed, first.latency_ms = CaseResult.Status.DONE, True, 900
    first.scores = {"refusal_rate": 1.0}
    first.save()
    return run


def test_at_0012_01_stopping_keeps_finished_cases_and_stops_the_rest(
    db, run, quiet, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        assert services.cancel_run(run) is True
    run.refresh_from_db()
    assert run.status == BenchmarkRun.Status.CANCELLED and run.finished_at is not None
    statuses = list(run.results.values_list("status", flat=True))
    assert statuses == ["done", "cancelled", "cancelled"]
    assert quiet.cancelled == ["hatchet-123"]  # the parent is cancelled in Hatchet too
    assert quiet.sent[-1] == {
        "type": "benchmark.completed",
        "run_id": run.pk,
        "status": "cancelled",
    }


def test_at_0012_02_a_stopped_run_never_passes_and_its_summary_is_partial(db, run):
    services.cancel_run(run)
    run.refresh_from_db()
    assert run.summary["partial"] is True
    assert (run.summary["done"], run.summary["total"], run.summary["stopped_cases"]) == (1, 3, 2)
    assert run.summary["metrics"]["latency_total"]["mean"] == 0.9  # only the finished case
    # The boundary would hold, but a stopped run's boundaries aren't checked.
    assert run.summary["boundaries"][0]["passed"] is None
    assert services.cancel_run(run) is False  # already stopped


def test_a_finished_run_cannot_be_stopped(db, run):
    services.finalize(run)
    assert services.cancel_run(run) is False
    run.refresh_from_db()
    assert run.status != BenchmarkRun.Status.CANCELLED


def test_a_result_arriving_after_stop_is_discarded(db, run, quiet):
    late = run.results.get(position=1)
    services.cancel_run(run)
    late.status, late.passed, late.answer = CaseResult.Status.DONE, True, "Too late"
    quiet.sent.clear()
    services.record_result(late)
    late.refresh_from_db()
    assert (late.status, late.answer) == ("cancelled", "")
    assert quiet.sent == []  # no benchmark.case for a stopped case


def test_the_parent_leaves_a_stopped_run_alone(db, run):
    services.cancel_run(run)
    services.finalize(BenchmarkRun.objects.get(pk=run.pk))
    run.refresh_from_db()
    assert run.status == BenchmarkRun.Status.CANCELLED and run.summary["partial"] is True


def test_at_0012_03_resume_reruns_only_the_stopped_cases(db, run):
    services.cancel_run(run)
    assert services.retry_failed(run) == 2
    run.refresh_from_db()
    assert run.status == BenchmarkRun.Status.RUNNING and run.finished_at is None
    assert list(run.results.values_list("status", flat=True)) == ["done", "pending", "pending"]


def test_a_case_mid_answer_stops_when_cancelled(db, run, monkeypatch):
    adapter = FakeAdapter([Text("It was "), Text("Brazil"), Done("end")])
    monkeypatch.setattr("apps.providers.services.build_adapter", lambda *a, **k: adapter)
    case = run.results.get(position=1)
    with pytest.raises(Cancelled):
        execution.execute(case, is_cancelled=lambda: True)


def test_the_cancel_check_reads_the_database_at_most_once_a_second(db, run, monkeypatch):
    calls = []
    monkeypatch.setattr(
        services, "is_case_cancelled", lambda result_id: calls.append(result_id) or False
    )
    ctx = SimpleNamespace(is_cancelled=False)
    check = tasks._cancel_check(run.results.get(position=1).pk, ctx)
    assert [check() for _ in range(50)] == [False] * 50
    assert len(calls) == 1
    ctx.is_cancelled = True  # Hatchet's own flag wins straight away
    assert check() is True


def test_is_case_cancelled_follows_the_run(db, run):
    case = run.results.get(position=1)
    assert services.is_case_cancelled(case.pk) is False
    services.cancel_run(run)
    assert services.is_case_cancelled(case.pk) is True


def test_at_0012_04_only_the_owner_can_stop_a_run(db, run, other_user, auth_api):
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.post(f"/api/benchmarks/runs/{run.pk}/cancel/").status_code == 404
    run.refresh_from_db()
    assert run.status == BenchmarkRun.Status.RUNNING
    assert auth_api.post(f"/api/benchmarks/runs/{run.pk}/cancel/").status_code == 202
    assert auth_api.post(f"/api/benchmarks/runs/{run.pk}/cancel/").status_code == 409
