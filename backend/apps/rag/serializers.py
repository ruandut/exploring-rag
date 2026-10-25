from rest_framework import serializers

from .models import IndexingConfig


class IndexingConfigSerializer(serializers.ModelSerializer):
    chunk_size = serializers.IntegerField(min_value=64, max_value=8192)
    chunk_overlap = serializers.IntegerField(min_value=0, max_value=4096)

    class Meta:
        model = IndexingConfig
        fields = ["strategy", "chunk_size", "chunk_overlap", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate(self, attrs):
        size = attrs.get("chunk_size", getattr(self.instance, "chunk_size", None))
        overlap = attrs.get("chunk_overlap", getattr(self.instance, "chunk_overlap", None))
        if size is not None and overlap is not None and overlap >= size:
            raise serializers.ValidationError(
                {"chunk_overlap": "Overlap must be smaller than the chunk size."}
            )
        return attrs


class SaveIndexingConfigSerializer(IndexingConfigSerializer):
    confirm_reindex = serializers.BooleanField(default=False, write_only=True)

    class Meta(IndexingConfigSerializer.Meta):
        fields = [*IndexingConfigSerializer.Meta.fields, "confirm_reindex"]


class ChunkSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    heading = serializers.CharField()
    text = serializers.CharField()
    parent_text = serializers.CharField()
    token_count = serializers.IntegerField()
    dimensions = serializers.IntegerField()
    embedding_model = serializers.CharField()
    # A peek at the vector itself — the first few numbers are enough to make it real.
    embedding_preview = serializers.SerializerMethodField()

    def get_embedding_preview(self, chunk) -> list[float]:
        return [round(float(x), 4) for x in chunk.embedding[:6]]
