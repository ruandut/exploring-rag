from openai import OpenAIError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from . import selectors, services
from .serializers import (
    ConnectionSerializer,
    ProviderConfigSerializer,
    SaveProviderSerializer,
    TestConnectionSerializer,
)


@api_view(["GET", "PUT"])
def provider_config(request):
    if request.method == "GET":
        config = selectors.get_provider_config(request.user)
        if config is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(ProviderConfigSerializer(config).data)

    payload = SaveProviderSerializer(
        instance=selectors.get_provider_config(request.user), data=request.data
    )
    payload.is_valid(raise_exception=True)
    data = dict(payload.validated_data)
    confirm = data.pop("confirm_reindex")
    try:
        config, reindex_started = services.save_provider_config(
            request.user, data=data, confirm_reindex=confirm
        )
    except services.ReindexConfirmationRequired:
        return Response(
            {
                "code": "reindex_required",
                "detail": "Changing the endpoint or embedding model re-indexes all your documents.",
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response({**ProviderConfigSerializer(config).data, "reindex_started": reindex_started})


@api_view(["POST"])
def test_connection(request):
    payload = TestConnectionSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    params = dict(payload.validated_data)
    if not params.get("api_key"):
        saved = selectors.get_provider_config(request.user)
        params["api_key"] = selectors.get_api_key(saved) if saved else ""
    return Response(services.test_connection(**params))


def _models_response(base_url: str, api_key: str) -> Response:
    try:
        return Response({"models": services.list_models(base_url, api_key)})
    except OpenAIError as exc:
        return Response({"detail": services.error_message(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
def default_models(request):
    """Models offered by the default provider."""
    config = selectors.get_provider_config(request.user)
    if config is None:
        return Response({"models": []})
    return _models_response(config.base_url, selectors.get_api_key(config))


class ConnectionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Extra OpenAI-compatible endpoints (e.g. a local Ollama) that agents can chat with."""

    serializer_class = ConnectionSerializer

    def get_queryset(self):
        return selectors.connections_for(self.request.user)

    def perform_create(self, serializer):
        serializer.instance = services.save_connection(
            self.request.user, data=serializer.validated_data
        )

    def perform_update(self, serializer):
        services.save_connection(
            self.request.user, data=serializer.validated_data, instance=serializer.instance
        )

    @action(detail=True, methods=["get"])
    def models(self, request, pk=None):
        """Lists the endpoint's models — doubles as a connection test."""
        conn = self.get_object()
        return _models_response(conn.base_url, selectors.get_api_key(conn))
