import uuid

from django.conf import settings
from django.db import models


class BenchmarkRun(models.Model):
    """One suite run against one target. Everything it depends on is snapshotted, so editing
    the suite or the agent later never changes what this run says."""

    class Status(models.TextChoices):
        RUNNING = "running"
        PASSED = "passed"
        FAILED = "failed"

    class TargetKind(models.TextChoices):
        AGENT = "agent"
        MODEL = "model"  # a bare model: no retrieval — the baseline

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="benchmark_runs"
    )
    # The live suite (may be edited or deleted); suite_snapshot is what was actually tested.
    suite = models.ForeignKey(
        "evals.EvalSuite", null=True, on_delete=models.SET_NULL, related_name="runs"
    )
    suite_snapshot = models.JSONField()
    target_kind = models.CharField(max_length=8, choices=TargetKind.choices)
    target_label = models.CharField(max_length=300)
    target_snapshot = models.JSONField()
    # Runs started together for a side-by-side comparison share a group.
    compare_group = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    summary = models.JSONField(default=dict)
    hatchet_run_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.suite_snapshot.get('name')} × {self.target_label}"

    @staticmethod
    def new_group() -> uuid.UUID:
        return uuid.uuid4()


class CaseResult(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        DONE = "done"
        FAILED = "failed"  # the target or judge errored — retryable

    run = models.ForeignKey(BenchmarkRun, on_delete=models.CASCADE, related_name="results")
    position = models.PositiveIntegerField()
    case = models.JSONField()  # the case as it was in the suite snapshot
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    answer = models.TextField(blank=True)
    retrieved = models.JSONField(default=list)  # de-duplicated, in first-retrieved order
    scores = models.JSONField(default=dict)  # metric id → value, or None for n/a
    explanations = models.JSONField(default=dict)  # metric id → maths or the judge's reasoning
    ttft_ms = models.PositiveIntegerField(null=True)
    latency_ms = models.PositiveIntegerField(null=True)
    tokens = models.PositiveIntegerField(null=True)
    # Where the answer's time went (spec 0011). The four phases add up to latency_ms exactly;
    # search_ms is None for a bare model (it can't search). Judge time is kept apart so it
    # never counts as the target's speed.
    waiting_ms = models.PositiveIntegerField(null=True)
    search_ms = models.PositiveIntegerField(null=True)
    reasoning_ms = models.PositiveIntegerField(null=True)
    writing_ms = models.PositiveIntegerField(null=True)
    judge_ms = models.PositiveIntegerField(null=True)
    tokens_per_second = models.FloatField(null=True)  # tokens ÷ writing time
    passed = models.BooleanField(null=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.run_id}:{self.position}"
