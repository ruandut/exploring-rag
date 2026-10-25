from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.library import selectors as library_selectors
from apps.library.models import Document
from apps.providers import selectors as provider_selectors
from apps.providers import services as provider_services
from apps.providers.models import Connection

from . import selectors, services
from .serializers import (
    ChunkSerializer,
    EmbeddingSerializer,
    EntrySerializer,
    SaveEmbeddingSerializer,
)

REINDEX_REQUIRED = {
    "code": "reindex_required",
    "detail": "Changing the endpoint, model, dimensions or chunking re-indexes this embedding.",
}


class EmbeddingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Named embeddings (spec 0010). Creating or editing one starts indexing on Hatchet."""

    def get_queryset(self):
        return selectors.embeddings_for(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SaveEmbeddingSerializer
        return EmbeddingSerializer

    def _fresh(self, pk: int) -> dict:
        index = selectors.get_embedding(self.request.user, pk)
        return EmbeddingSerializer(index, context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        data.pop("confirm_reindex", None)
        index = services.create_embedding(request.user, data=data)
        return Response(self._fresh(index.pk), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        payload = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        confirm = data.pop("confirm_reindex", False)
        try:
            index, reindex_started = services.update_embedding(
                payload.instance, data=data, confirm_reindex=confirm
            )
        except services.ReindexConfirmationRequired:
            return Response(REINDEX_REQUIRED, status=status.HTTP_409_CONFLICT)
        return Response({**self._fresh(index.pk), "reindex_started": reindex_started})

    def perform_destroy(self, instance):
        services.delete_embedding(instance)

    @action(detail=True, methods=["post"])
    def reindex(self, request, pk=None):
        services.reindex_embedding(self.get_object())
        return Response(self._fresh(int(pk)), status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        """Which documents the embedding covers, and how far each one is."""
        entries = selectors.entries_for(self.get_object()).order_by("document__name")
        return Response(EntrySerializer(entries, many=True).data)

    @action(detail=False, methods=["post"])
    def test(self, request):
        """One embedding call with the (possibly unsaved) form's endpoint + model."""
        model = str(request.data.get("model", "")).strip()
        if not model:
            return Response({"model": ["Pick a model."]}, status=status.HTTP_400_BAD_REQUEST)
        connection = None
        if request.data.get("connection"):
            try:
                connection = provider_selectors.get_connection(
                    request.user, int(request.data["connection"])
                )
            except (ValueError, Connection.DoesNotExist) as exc:
                raise NotFound("Connection not found") from exc
        try:
            client = provider_services.embedding_client(request.user, connection)
        except ValueError as exc:
            return Response(
                {"ok": False, "detail": str(exc), "latency_ms": None, "dimensions": None}
            )
        return Response(provider_services.test_embedding(client=client, model=model))


@api_view(["GET"])
def document_chunks(request, document_id: int):
    """What indexing produced for one document: every chunk, its size and a vector preview.
    ?embedding=<id> picks the embedding; the oldest one covering the document by default."""
    try:
        library_selectors.get_document(request.user, document_id)
    except Document.DoesNotExist as exc:
        raise NotFound("Document not found") from exc
    raw = request.query_params.get("embedding")
    embedding_id = int(raw) if raw and raw.isdigit() else None
    chunks = selectors.chunks_for_document(request.user, document_id, embedding_id)
    return Response(ChunkSerializer(chunks, many=True).data)
