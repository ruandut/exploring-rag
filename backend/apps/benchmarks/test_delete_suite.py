"""Deleting a suite keeps its runs (spec 0014) — no Hatchet, no network."""

import pytest
from rest_framework.test import APIClient

from apps.benchmarks import services
from apps.benchmarks.models import BenchmarkRun, CaseResult
from apps.evals import services as eval_services
from apps.evals.models import EvalCase, EvalSuite
from apps.providers.models import ProviderConfig

CASES = [
    {"kind": "refusal", "question": "Who won the 2030 World Cup?"},
    {"kind": "refusal", "question": "Who won the 2034 World Cup?"},
]


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(services, "_launch", lambda run, ids: None)
    monkeypatch.setattr(services, "send_to_user", lambda *a: None)


@pytest.fixture
def suite(user):
    ProviderConfig.objects.create(owner=user, base_url="http://fake/v1", chat_model="fake-chat")
    return eval_services.save_suite(user, data={"name": "Bible", "metrics": [], "cases": CASES})


def test_at_0014_01_deleting_a_suite_keeps_its_runs(db, user, suite, auth_api):
    [run] = services.start_runs(user, suite, [{"kind": "model", "model": "fake-chat"}])
    assert auth_api.delete(f"/api/evals/suites/{suite.pk}/").status_code == 204

    assert not EvalSuite.objects.filter(pk=suite.pk).exists()
    assert not EvalCase.objects.filter(suite_id=suite.pk).exists()  # cases go with it
    run.refresh_from_db()
    assert run.suite is None
    assert run.suite_snapshot["name"] == "Bible"  # still readable from its snapshot
    assert CaseResult.objects.filter(run=run).count() == 2

    listed = auth_api.get("/api/benchmarks/runs/?suite=deleted").json()
    assert [(r["id"], r["suite_name"]) for r in listed] == [(run.pk, "Bible")]
    assert auth_api.get(f"/api/benchmarks/runs/{run.pk}/").status_code == 200


def test_runs_of_live_suites_are_not_listed_as_deleted(db, user, suite, auth_api):
    services.start_runs(user, suite, [{"kind": "model", "model": "fake-chat"}])
    assert auth_api.get("/api/benchmarks/runs/?suite=deleted").json() == []


def test_at_0014_03_a_running_run_finishes_after_its_suite_is_deleted(db, user, suite):
    [run] = services.start_runs(user, suite, [{"kind": "model", "model": "fake-chat"}])
    eval_services.delete_suite(suite)
    run.refresh_from_db()
    run.results.update(status=CaseResult.Status.DONE, passed=True, scores={"refusal_rate": 1.0})
    run = services.finalize(run)  # scored from the snapshot, not the deleted suite
    assert run.status == BenchmarkRun.Status.PASSED


def test_at_0014_04_only_the_owner_can_delete_a_suite(db, user, other_user, suite, auth_api):
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.delete(f"/api/evals/suites/{suite.pk}/").status_code == 404
    assert EvalSuite.objects.filter(pk=suite.pk).exists()
    # Nor do other people's deleted-suite runs show up.
    [run] = services.start_runs(user, suite, [{"kind": "model", "model": "fake-chat"}])
    eval_services.delete_suite(suite)
    assert bob.get("/api/benchmarks/runs/?suite=deleted").json() == []
    assert bob.get(f"/api/benchmarks/runs/{run.pk}/").status_code == 404
