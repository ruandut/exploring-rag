"""Write-side logic for suites. Cases and boundaries are saved together with their suite (the
editor sends the whole suite), and every save bumps the suite's version."""

import json

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Boundary, CaseKind, EvalCase, EvalSuite

CASE_FIELDS = ("kind", "question", "reference_answer", "relevant_documents", "evidence")


@transaction.atomic
def save_suite(user, *, data: dict, instance: EvalSuite | None = None) -> EvalSuite:
    suite = instance or EvalSuite(owner=user)
    for field in ("name", "description", "metrics", "k", "judge_connection", "judge_model"):
        if field in data:
            setattr(suite, field, data[field])
    if instance is not None:
        suite.version += 1
    suite.save()

    if "cases" in data:
        suite.cases.all().delete()
        EvalCase.objects.bulk_create(
            EvalCase(suite=suite, position=i, **{f: c.get(f, "") for f in CASE_FIELDS if f in c})
            for i, c in enumerate(data["cases"])
        )
    if "boundaries" in data:
        suite.boundaries.all().delete()
        Boundary.objects.bulk_create(Boundary(suite=suite, **b) for b in data["boundaries"])
    return suite


def delete_suite(suite: EvalSuite) -> None:
    """Delete a suite with its cases and boundaries (spec 0014). Its benchmark runs are kept:
    each carries a snapshot of the suite it tested, and benchmarks lists them as runs of
    deleted suites (the run's link to the suite is SET_NULL)."""
    suite.delete()


def parse_jsonl(text: str) -> list[dict]:
    """One case per line, e.g.
    {"kind": "qa", "question": "…", "reference_answer": "…", "relevant_documents": ["a.md"],
     "evidence": "…"}. Only "question" is required; kind defaults to "qa"."""
    cases = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Line {number} isn't valid JSON: {exc.msg}") from exc
        if not isinstance(row, dict) or not str(row.get("question", "")).strip():
            raise ValidationError(f'Line {number} needs a "question"')
        kind = row.get("kind", CaseKind.QA)
        if kind not in CaseKind.values:
            raise ValidationError(f"Line {number}: unknown kind {kind!r}")
        docs = row.get("relevant_documents", [])
        cases.append(
            {
                "kind": kind,
                "question": str(row["question"]).strip(),
                "reference_answer": str(row.get("reference_answer", "")),
                "relevant_documents": [
                    str(d) for d in (docs if isinstance(docs, list) else [docs])
                ],
                "evidence": str(row.get("evidence", "")),
            }
        )
    return cases


@transaction.atomic
def import_cases(suite: EvalSuite, text: str) -> int:
    cases = parse_jsonl(text)
    start = suite.cases.count()
    EvalCase.objects.bulk_create(
        EvalCase(suite=suite, position=start + i, **c) for i, c in enumerate(cases)
    )
    suite.version += 1
    suite.save(update_fields=["version", "updated_at"])
    return len(cases)


def export_cases(suite: EvalSuite) -> str:
    return "".join(
        json.dumps({f: getattr(c, f) for f in CASE_FIELDS}, ensure_ascii=False) + "\n"
        for c in suite.cases.all()
    )
