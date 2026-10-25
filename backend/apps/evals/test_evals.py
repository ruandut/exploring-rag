import json

import pytest
from rest_framework.test import APIClient

from apps.evals.models import EvalSuite
from apps.providers.models import Connection

SUITE = {
    "name": "Basics",
    "metrics": ["faithfulness", "recall"],
    "cases": [
        {
            "kind": "qa",
            "question": "What is the refund window?",
            "reference_answer": "30 days",
            "relevant_documents": ["handbook.md"],
            "evidence": "refund window is 30",
        },
        {"kind": "refusal", "question": "Who won the 2030 World Cup?"},
    ],
    "boundaries": [
        {"metric": "faithfulness", "aggregate": "mean", "comparator": "gte", "value": 0.9}
    ],
}


@pytest.fixture
def suite(auth_api):
    res = auth_api.post("/api/evals/suites/", SUITE, format="json")
    assert res.status_code == 201, res.content
    return res.json()


def test_create_suite_with_cases_and_boundaries(auth_api, suite):
    detail = auth_api.get(f"/api/evals/suites/{suite['id']}/").json()
    assert [c["kind"] for c in detail["cases"]] == ["qa", "refusal"]
    assert detail["boundaries"][0]["metric"] == "faithfulness"
    assert detail["k"] == 5 and detail["version"] == 1
    assert auth_api.get("/api/evals/suites/").json()[0]["case_count"] == 2


def test_saving_bumps_the_version(auth_api, suite):
    res = auth_api.put(
        f"/api/evals/suites/{suite['id']}/", {**SUITE, "description": "v2"}, format="json"
    )
    assert res.json()["version"] == 2


def test_unknown_metrics_are_rejected(auth_api):
    res = auth_api.post("/api/evals/suites/", {**SUITE, "metrics": ["vibes"]}, format="json")
    assert res.status_code == 400


def test_a_judge_connection_needs_a_model(auth_api, user):
    conn = Connection.objects.create(owner=user, name="Local", base_url="http://x/v1")
    res = auth_api.post("/api/evals/suites/", {**SUITE, "judge_connection": conn.pk}, format="json")
    assert res.status_code == 400 and "judge_model" in res.json()


def test_jsonl_import_and_export_round_trip(auth_api, suite):
    lines = "\n".join(
        json.dumps({"question": f"Q{i}?", "relevant_documents": ["a.md"]}) for i in range(3)
    )
    res = auth_api.post(f"/api/evals/suites/{suite['id']}/import/", {"text": lines}, format="json")
    assert res.json() == {"added": 3}
    exported = auth_api.get(f"/api/evals/suites/{suite['id']}/export/").content.decode()
    rows = [json.loads(line) for line in exported.splitlines()]
    assert len(rows) == 5 and rows[-1]["question"] == "Q2?" and rows[-1]["kind"] == "qa"


def test_bad_jsonl_names_the_line(auth_api, suite):
    res = auth_api.post(
        f"/api/evals/suites/{suite['id']}/import/",
        {"text": '{"question": "ok"}\nnot json'},
        format="json",
    )
    assert res.status_code == 400 and "Line 2" in res.json()["detail"]
    assert EvalSuite.objects.get().cases.count() == 2  # nothing half-imported


def test_suites_are_private(suite, other_user):
    bob = APIClient()
    bob.force_authenticate(other_user)
    assert bob.get("/api/evals/suites/").json() == []
    assert bob.get(f"/api/evals/suites/{suite['id']}/").status_code == 404
