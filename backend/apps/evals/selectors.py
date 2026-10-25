from django.db.models import Count, QuerySet

from .models import EvalSuite


def suites_for(user) -> QuerySet[EvalSuite]:
    return (
        EvalSuite.objects.filter(owner=user)
        .select_related("judge_connection")
        .annotate(case_count=Count("cases", distinct=True))
    )


def get_suite(user, suite_id: int) -> EvalSuite:
    return (
        EvalSuite.objects.filter(owner=user)
        .select_related("judge_connection")
        .prefetch_related("cases", "boundaries")
        .get(pk=suite_id)
    )


def snapshot(suite: EvalSuite) -> dict:
    """Everything a run needs, frozen — editing the suite later doesn't change old results."""
    return {
        "name": suite.name,
        "version": suite.version,
        "metrics": list(suite.metrics),
        "k": suite.k,
        "judge_connection": suite.judge_connection_id,
        "judge_model": suite.judge_model,
        "cases": [
            {
                "id": c.pk,
                "kind": c.kind,
                "question": c.question,
                "reference_answer": c.reference_answer,
                "relevant_documents": list(c.relevant_documents),
                "evidence": c.evidence,
            }
            for c in suite.cases.all()
        ],
        "boundaries": [
            {
                "metric": b.metric,
                "aggregate": b.aggregate,
                "comparator": b.comparator,
                "value": b.value,
            }
            for b in suite.boundaries.all()
        ],
    }
