from django.db.models import ProtectedError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from . import catalog, selectors, services
from .llm import ProviderError
from .models import ProviderKind
from .serializers import (
    ConnectionSerializer,
    ProviderConfigSerializer,
    TestConnectionSerializer,
)


@api_view(["GET", "PUT"])
def provider_config(request):
    if request.method == "GET":
        config = selectors.get_provider_config(request.user)
        if config is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(ProviderConfigSerializer(config).data)

    payload = ProviderConfigSerializer(
        instance=selectors.get_provider_config(request.user), data=request.data
    )
    payload.is_valid(raise_exception=True)
    config = services.save_provider_config(request.user, data=dict(payload.validated_data))
    return Response(ProviderConfigSerializer(config).data)


@api_view(["POST"])
def test_connection(request):
    payload = TestConnectionSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    params = {"base_url": "", **payload.validated_data}
    if not params.get("api_key"):
        # A blank key means "the saved one" — but only if it belongs to the same kind.
        saved = selectors.get_provider_config(request.user)
        params["api_key"] = (
            selectors.get_api_key(saved) if saved and saved.kind == params["kind"] else ""
        )
    return Response(services.test_connection(**params))


def _models_response(request, adapter) -> Response:
    """The model picker's list: every model with its kind (see catalog.py). ?kind=embedding or
    ?kind=chat keeps that kind (plus unknowns); no kind = all."""
    want = request.query_params.get("kind") or (
        request.data.get("kind") if request.method == "POST" else None
    )
    try:
        return Response(catalog.catalogue(adapter, want=want))
    except ProviderError as exc:
        return Response({"detail": services.error_message(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
def default_models(request):
    """Models offered by the default provider."""
    config = selectors.get_provider_config(request.user)
    if config is None:
        return Response({"endpoint": "", "hint": "", "models": []})
    return _models_response(request, services.adapter_for(request.user, None, timeout=10.0))


@api_view(["POST"])
def probe_models(request):
    """Models of an endpoint that isn't saved yet (the Settings form). A blank api_key means
    the saved provider's key, like Test connection."""
    kind = str(request.data.get("kind", ProviderKind.OPENAI))
    if kind not in ProviderKind.values:
        return Response({"kind": ["Unknown provider kind."]}, status=status.HTTP_400_BAD_REQUEST)
    base_url = str(request.data.get("base_url", "")).strip()
    if (
        base_url
        and not base_url.startswith(("http://", "https://"))
        or (kind == ProviderKind.OPENAI and not base_url)
    ):
        return Response({"base_url": ["Enter a URL."]}, status=status.HTTP_400_BAD_REQUEST)
    api_key = str(request.data.get("api_key", "") or "")
    if not api_key:
        saved = selectors.get_provider_config(request.user)
        api_key = selectors.get_api_key(saved) if saved and saved.kind == kind else ""
    return _models_response(request, services.build_adapter(kind, base_url, api_key, timeout=10.0))


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

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            # An embedding still embeds through it; deleting would strand its vectors.
            return Response(
                {"detail": "An embedding uses this connection. Change or delete it first."},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=True, methods=["get"])
    def models(self, request, pk=None):
        """Lists the endpoint's models — doubles as a connection test."""
        conn = self.get_object()
        return _models_response(request, services.adapter_for(request.user, conn, timeout=10.0))
