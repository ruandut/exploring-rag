from rest_framework import serializers

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

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "system_message",
            "effort",
            "rag_config",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate_name(self, name):
        user = self.context["request"].user
        clash = Agent.objects.filter(owner=user, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("You already have an agent with this name.")
        return name
