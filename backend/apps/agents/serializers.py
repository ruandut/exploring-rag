from rest_framework import serializers

from apps.library.models import Folder
from apps.providers.models import Connection

from .models import (
    GENERATION_STRATEGIES,
    QUERY_TRANSFORMS,
    RERANKERS,
    RETRIEVAL_METHODS,
    Agent,
)


class RagConfigSerializer(serializers.Serializer):
    query_transform = serializers.ChoiceField(QUERY_TRANSFORMS, default="none")
    retrieval = serializers.ChoiceField(RETRIEVAL_METHODS, default="hybrid")
    top_k = serializers.IntegerField(min_value=1, max_value=20, default=5)
    rerank = serializers.ChoiceField(RERANKERS, default="none")
    generation = serializers.ChoiceField(GENERATION_STRATEGIES, default="cited")


class AgentSerializer(serializers.ModelSerializer):
    rag_config = RagConfigSerializer(required=False)
    connection = serializers.PrimaryKeyRelatedField(
        queryset=Connection.objects.none(), allow_null=True, required=False
    )
    folders = serializers.PrimaryKeyRelatedField(
        queryset=Folder.objects.none(), many=True, required=False
    )
    connection_name = serializers.CharField(source="connection.name", read_only=True, default=None)

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "system_message",
            "connection",
            "connection_name",
            "model",
            "folders",
            "rag_config",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the requesting user's own connections and folders are valid choices.
        user = self.context["request"].user
        self.fields["connection"].queryset = Connection.objects.filter(owner=user)
        self.fields["folders"].child_relation.queryset = Folder.objects.filter(owner=user)

    def validate_name(self, name):
        user = self.context["request"].user
        clash = Agent.objects.filter(owner=user, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("You already have an agent with this name.")
        return name

    def validate(self, attrs):
        connection = attrs.get("connection", getattr(self.instance, "connection", None))
        model = attrs.get("model", getattr(self.instance, "model", ""))
        if connection is not None and not model:
            raise serializers.ValidationError({"model": "Pick a model for this connection."})
        return attrs
