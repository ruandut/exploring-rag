from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from . import selectors, services
from .models import Folder
from .serializers import DocumentSerializer, FolderSerializer, UploadSerializer


def _drf(exc: DjangoValidationError) -> ValidationError:
    return ValidationError({"detail": exc.messages[0]})


class FolderViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Flat list; the client builds the tree from `parent`."""

    serializer_class = FolderSerializer

    def get_queryset(self):
        return selectors.folders_for(self.request.user)

    def perform_create(self, serializer):
        try:
            serializer.instance = services.create_folder(
                self.request.user,
                name=serializer.validated_data["name"],
                parent=serializer.validated_data.get("parent"),
            )
        except DjangoValidationError as exc:
            raise _drf(exc) from exc

    def perform_update(self, serializer):
        data = serializer.validated_data
        kwargs = {"name": data.get("name")}
        if "parent" in data:
            kwargs["parent"] = data["parent"]
        try:
            services.update_folder(serializer.instance, **kwargs)
        except DjangoValidationError as exc:
            raise _drf(exc) from exc

    def perform_destroy(self, instance):
        services.delete_folder(instance)


class DocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DocumentSerializer
    parser_classes = [JSONParser, MultiPartParser]

    def get_queryset(self):
        return selectors.documents_for(
            self.request.user, folder=self.request.query_params.get("folder")
        )

    def create(self, request):
        """Multipart upload: `files` (one or more) and optional `folder` id."""
        payload = UploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        folder_id = payload.validated_data.get("folder")
        try:
            folder = selectors.get_folder(request.user, folder_id) if folder_id else None
        except Folder.DoesNotExist as exc:
            raise NotFound("Folder not found") from exc
        try:
            docs = services.upload_documents(
                request.user, files=payload.validated_data["files"], folder=folder
            )
        except DjangoValidationError as exc:
            raise _drf(exc) from exc
        return Response(DocumentSerializer(docs, many=True).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        try:
            services.move_document(
                serializer.instance, folder=serializer.validated_data.get("folder")
            )
        except DjangoValidationError as exc:
            raise _drf(exc) from exc

    def perform_destroy(self, instance):
        services.delete_document(instance)

    @action(detail=True, methods=["post"])
    def reindex(self, request, pk=None):
        doc = services.request_reindex(self.get_object())
        return Response(DocumentSerializer(doc).data, status=status.HTTP_202_ACCEPTED)
