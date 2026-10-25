from rest_framework import serializers

from apps.providers.models import Connection
from apps.scoring.metrics import METRICS, SELECTABLE

from .models import Boundary, CaseKind, EvalCase, EvalSuite


class CaseSerializer(serializers.ModelSerializer):
    relevant_documents = serializers.ListField(
        child=serializers.CharField(max_length=255), required=False, default=list
    )

    class Meta:
        model = EvalCase
        fields = ["id", "kind", "question", "reference_answer", "relevant_documents", "evidence"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if (
            attrs.get("kind", CaseKind.QA) == CaseKind.QA
            and attrs.get("evidence")
            and not attrs.get("relevant_documents")
        ):
            raise serializers.ValidationError(
                {"relevant_documents": "Evidence needs the document it's in."}
            )
        return attrs


class BoundarySerializer(serializers.ModelSerializer):
    metric = serializers.ChoiceField(choices=list(METRICS))

    class Meta:
        model = Boundary
        fields = ["metric", "aggregate", "comparator", "value"]


class SuiteSerializer(serializers.ModelSerializer):
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=SELECTABLE), required=False
    )
    k = serializers.IntegerField(min_value=1, max_value=50, required=False)
    cases = CaseSerializer(many=True, required=False)
    boundaries = BoundarySerializer(many=True, required=False)
    judge_connection = serializers.PrimaryKeyRelatedField(
        queryset=Connection.objects.none(), allow_null=True, required=False
    )
    case_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = EvalSuite
        fields = [
            "id",
            "name",
            "description",
            "metrics",
            "k",
            "judge_connection",
            "judge_model",
            "version",
            "case_count",
            "cases",
            "boundaries",
            "updated_at",
        ]
        read_only_fields = ["id", "version", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context["request"].user
        self.fields["judge_connection"].queryset = Connection.objects.filter(owner=user)

    def validate_name(self, name):
        clash = EvalSuite.objects.filter(owner=self.context["request"].user, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("You already have a suite with this name.")
        return name

    def validate(self, attrs):
        conn = attrs.get("judge_connection", getattr(self.instance, "judge_connection", None))
        model = attrs.get("judge_model", getattr(self.instance, "judge_model", ""))
        if conn is not None and not model:
            raise serializers.ValidationError({"judge_model": "Pick a model for the judge."})
        return attrs


class SuiteListSerializer(serializers.ModelSerializer):
    case_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = EvalSuite
        fields = [
            "id",
            "name",
            "description",
            "metrics",
            "k",
            "version",
            "case_count",
            "updated_at",
        ]
