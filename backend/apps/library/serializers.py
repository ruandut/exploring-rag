from rest_framework import serializers

from .models import Document, Folder


class FolderSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Folder
        fields = ["id", "name", "parent", "document_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_parent(self, parent):
        request = self.context["request"]
        if parent is not None and parent.owner_id != request.user.id:
            raise serializers.ValidationError("Folder not found")
        return parent


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "folder",
            "content_type",
            "size",
            "status",
            "error",
            "chunk_count",
            "indexed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [f for f in fields if f != "folder"]

    def validate_folder(self, folder):
        request = self.context["request"]
        if folder is not None and folder.owner_id != request.user.id:
            raise serializers.ValidationError("Folder not found")
        return folder


class UploadSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False, max_length=50)
    folder = serializers.IntegerField(required=False, allow_null=True)
