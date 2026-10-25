from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from . import selectors, services
from .serializers import SuiteListSerializer, SuiteSerializer


class SuiteViewSet(viewsets.ModelViewSet):
    """Suites with their cases and boundaries (the editor saves them together)."""

    parser_classes = [JSONParser, MultiPartParser]

    def get_queryset(self):
        qs = selectors.suites_for(self.request.user)
        return qs.prefetch_related("cases", "boundaries") if self.action != "list" else qs

    def get_serializer_class(self):
        return SuiteListSerializer if self.action == "list" else SuiteSerializer

    def perform_create(self, serializer):
        serializer.instance = services.save_suite(self.request.user, data=serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.save_suite(
            self.request.user, data=serializer.validated_data, instance=serializer.instance
        )

    @action(detail=True, methods=["post"], url_path="import")
    def import_cases(self, request, pk=None):
        """Append cases from a JSONL file (multipart `file`) or raw text (`text`)."""
        suite = self.get_object()
        upload = request.FILES.get("file")
        text = (
            upload.read().decode("utf-8", errors="replace")
            if upload
            else request.data.get("text", "")
        )
        try:
            added = services.import_cases(suite, text)
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages[0]}) from exc
        return Response({"added": added}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="export")
    def export_cases(self, request, pk=None):
        suite = self.get_object()
        response = HttpResponse(services.export_cases(suite), content_type="application/x-ndjson")
        response["Content-Disposition"] = f'attachment; filename="{suite.name}.jsonl"'
        return response
