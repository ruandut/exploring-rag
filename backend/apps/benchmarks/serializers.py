from rest_framework import serializers

from .models import BenchmarkRun, CaseResult


class CaseResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseResult
        fields = [
            "id",
            "position",
            "case",
            "status",
            "answer",
            "retrieved",
            "scores",
            "explanations",
            "ttft_ms",
            "latency_ms",
            "tokens",
            "passed",
            "error",
        ]


class RunSerializer(serializers.ModelSerializer):
    suite_name = serializers.CharField(source="suite_snapshot.name", read_only=True)

    class Meta:
        model = BenchmarkRun
        fields = [
            "id",
            "suite",
            "suite_name",
            "target_kind",
            "target_label",
            "compare_group",
            "status",
            "summary",
            "created_at",
            "finished_at",
        ]


class RunDetailSerializer(RunSerializer):
    results = CaseResultSerializer(many=True, read_only=True)
    siblings = serializers.SerializerMethodField()

    class Meta(RunSerializer.Meta):
        fields = [
            *RunSerializer.Meta.fields,
            "suite_snapshot",
            "target_snapshot",
            "hatchet_run_id",
            "results",
            "siblings",
        ]

    def get_siblings(self, run) -> list[int]:
        """Other runs started together with this one (side-by-side comparison)."""
        if not run.compare_group:
            return []
        return list(
            BenchmarkRun.objects.filter(compare_group=run.compare_group, owner=run.owner)
            .exclude(pk=run.pk)
            .values_list("pk", flat=True)
        )


class TargetSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["agent", "model"])
    agent = serializers.IntegerField(required=False)
    connection = serializers.IntegerField(required=False, allow_null=True)
    model = serializers.CharField(required=False, allow_blank=True)


class StartRunSerializer(serializers.Serializer):
    suite = serializers.IntegerField()
    targets = TargetSerializer(many=True, min_length=1, max_length=2)
