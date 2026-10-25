from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.library import selectors as library_selectors
from apps.library.models import Document

from . import selectors, services
from .serializers import ChunkSerializer, IndexingConfigSerializer, SaveIndexingConfigSerializer


@api_view(["GET", "PUT"])
def indexing_config(request):
    config = selectors.get_indexing_config(request.user)
    if request.method == "GET":
        return Response(IndexingConfigSerializer(config).data)

    payload = SaveIndexingConfigSerializer(instance=config, data=request.data)
    payload.is_valid(raise_exception=True)
    data = dict(payload.validated_data)
    confirm = data.pop("confirm_reindex")
    try:
        config, reindex_started = services.save_indexing_config(
            request.user, data=data, confirm_reindex=confirm
        )
    except services.ReindexConfirmationRequired:
        return Response(
            {
                "code": "reindex_required",
                "detail": "Changing chunking settings re-indexes all your documents.",
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response({**IndexingConfigSerializer(config).data, "reindex_started": reindex_started})


@api_view(["GET"])
def document_chunks(request, document_id: int):
    """What indexing produced for one document: every chunk, its size and a vector preview."""
    try:
        library_selectors.get_document(request.user, document_id)
    except Document.DoesNotExist as exc:
        raise NotFound("Document not found") from exc
    chunks = selectors.chunks_for_document(request.user, document_id)
    return Response(ChunkSerializer(chunks, many=True).data)
