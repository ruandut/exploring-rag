from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.evals import selectors as eval_selectors
from apps.evals.models import EvalSuite

from . import selectors, services
from .models import BenchmarkRun
from .serializers import RunDetailSerializer, RunSerializer, StartRunSerializer


class RunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Start runs (POST), list them (?suite=id), read results, retry failed cases."""

    def get_queryset(self):
        qs = BenchmarkRun.objects.filter(owner=self.request.user)
        suite = self.request.query_params.get("suite")
        if suite:
            qs = qs.filter(suite_id=suite)
        return qs.prefetch_related("results") if self.action == "retrieve" else qs

    def get_serializer_class(self):
        return RunDetailSerializer if self.action == "retrieve" else RunSerializer

    def create(self, request):
        payload = StartRunSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            suite = eval_selectors.get_suite(request.user, payload.validated_data["suite"])
        except EvalSuite.DoesNotExist as exc:
            raise NotFound("Suite not found") from exc
        try:
            runs = services.start_runs(request.user, suite, payload.validated_data["targets"])
        except services.InvalidTarget as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(RunSerializer(runs, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        retried = services.retry_failed(self.get_object())
        return Response({"retried": retried}, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
def model_speed(request):
    """One row per model: how fast it answered across all your finished runs (spec 0011)."""
    return Response(selectors.model_speed(request.user))
