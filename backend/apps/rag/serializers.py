from rest_framework import serializers

from apps.library.models import Document, Folder
from apps.providers.models import Connection

from .models import EmbeddingIndex, IndexedDocument


class EmbeddingSerializer(serializers.ModelSerializer):
    connection = serializers.PrimaryKeyRelatedField(
        queryset=Connection.objects.none(), allow_null=True, required=False
    )
    connection_name = serializers.SerializerMethodField()
    folders = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.none(), many=True, required=False
    )
    documents = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.none(), many=True, required=False
    )
    chunk_size = serializers.IntegerField(min_value=64, max_value=8192, required=False)
    chunk_overlap = serializers.IntegerField(min_value=0, max_value=4096, required=False)
    dimensions = serializers.IntegerField(
        min_value=1, max_value=16000, allow_null=True, required=False
    )
    done = serializers.IntegerField(read_only=True, default=0)
    total = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = EmbeddingIndex
        fields = [
            "id",
            "name",
            "connection",
            "connection_name",
            "model",
            "dimensions",
            "strategy",
            "chunk_size",
            "chunk_overlap",
            "all_documents",
            "folders",
            "documents",
            "status",
            "error",
            "done",
            "total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "error", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the requesting user's own connections, folders and files are valid choices.
        user = self.context["request"].user
        self.fields["connection"].queryset = Connection.objects.filter(owner=user)
        self.fields["folders"].child_relation.queryset = Folder.objects.filter(owner=user)
        self.fields["documents"].child_relation.queryset = Document.objects.filter(owner=user)

    def get_connection_name(self, obj) -> str:
        return obj.connection.name if obj.connection_id else "Default provider"

    def validate_name(self, name):
        user = self.context["request"].user
        clash = EmbeddingIndex.objects.filter(owner=user, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("You already have an embedding with this name.")
        return name

    def validate(self, attrs):
        size = attrs.get("chunk_size", getattr(self.instance, "chunk_size", 512))
        overlap = attrs.get("chunk_overlap", getattr(self.instance, "chunk_overlap", 64))
        if overlap >= size:
            raise serializers.ValidationError(
                {"chunk_overlap": "Overlap must be smaller than the chunk size."}
            )
        if not any(self._final(attrs, f) for f in ("all_documents", "folders", "documents")):
            raise serializers.ValidationError(
                {"folders": "Pick at least one folder or file, or all documents."}
            )
        return attrs

    def _final(self, attrs, field):
        """The value after this save: submitted, else what's stored."""
        if field in attrs:
            return attrs[field]
        if self.instance is None:
            return None
        value = getattr(self.instance, field)
        return value.exists() if field != "all_documents" else value


class SaveEmbeddingSerializer(EmbeddingSerializer):
    confirm_reindex = serializers.BooleanField(default=False, write_only=True)

    class Meta(EmbeddingSerializer.Meta):
        fields = [*EmbeddingSerializer.Meta.fields, "confirm_reindex"]


class EntrySerializer(serializers.ModelSerializer):
    document_id = serializers.IntegerField(source="document.pk")
    name = serializers.CharField(source="document.name")
    folder = serializers.IntegerField(source="document.folder_id", allow_null=True)

    class Meta:
        model = IndexedDocument
        fields = ["document_id", "name", "folder", "status", "error", "chunk_count", "indexed_at"]


class ChunkSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    heading = serializers.CharField()
    text = serializers.CharField()
    parent_text = serializers.CharField()
    token_count = serializers.IntegerField()
    dimensions = serializers.IntegerField()
    embedding_model = serializers.CharField()
    embedding_id = serializers.IntegerField(source="embedding_index_id")
    embedding_name = serializers.CharField(source="embedding_index.name")
    # A peek at the vector itself — the first few numbers are enough to make it real.
    embedding_preview = serializers.SerializerMethodField()

    def get_embedding_preview(self, chunk) -> list[float]:
        return [round(float(x), 4) for x in chunk.embedding[:6]]
