from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class CaseKind(models.TextChoices):
    QA = "qa", "Question & answer"
    REFUSAL = "refusal", "Should refuse"


class EvalSuite(TimeStampedModel):
    """What to test: cases + selected metrics + boundaries + who judges. Reusable across any
    target (agent or bare model) — it describes questions, not an agent."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="eval_suites"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    metrics = models.JSONField(default=list)  # ids from apps.scoring.metrics.SELECTABLE
    k = models.PositiveSmallIntegerField(default=5)  # cut-off for @k retrieval metrics
    # The judge: None = the default provider's chat model (or judge_model on it).
    judge_connection = models.ForeignKey(
        "providers.Connection", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    judge_model = models.CharField(max_length=200, blank=True)
    # Bumped on every change, so a run records exactly which version it tested.
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="evals_suite_unique_name"),
        ]

    def __str__(self):
        return self.name


class EvalCase(models.Model):
    suite = models.ForeignKey(EvalSuite, on_delete=models.CASCADE, related_name="cases")
    position = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=16, choices=CaseKind.choices, default=CaseKind.QA)
    question = models.TextField()
    reference_answer = models.TextField(blank=True)
    # Relevance is by document name (+ optional evidence text), never by chunk number —
    # chunk numbers change on every re-index.
    relevant_documents = models.JSONField(default=list, blank=True)
    evidence = models.TextField(blank=True)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.question[:60]


class Boundary(models.Model):
    class Aggregate(models.TextChoices):
        MEAN = "mean"
        P50 = "p50"
        P95 = "p95"

    class Comparator(models.TextChoices):
        GTE = "gte", "≥"
        LTE = "lte", "≤"

    suite = models.ForeignKey(EvalSuite, on_delete=models.CASCADE, related_name="boundaries")
    metric = models.CharField(max_length=40)
    aggregate = models.CharField(max_length=8, choices=Aggregate.choices, default=Aggregate.MEAN)
    comparator = models.CharField(max_length=4, choices=Comparator.choices, default=Comparator.GTE)
    value = models.FloatField()

    def __str__(self):
        return f"{self.metric} {self.aggregate} {self.get_comparator_display()} {self.value}"
