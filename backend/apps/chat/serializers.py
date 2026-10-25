from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "status", "run_id", "metadata", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    agent_name = serializers.SerializerMethodField()
    message_count = serializers.IntegerField(read_only=True, default=0)
    embedding_deleted = serializers.SerializerMethodField()
    connection_name = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "agent_key",
            "agent_name",
            "embedding",
            "embedding_name",
            "embedding_deleted",
            "connection",
            "connection_name",
            "model",
            "message_count",
            "updated_at",
        ]

    def get_embedding_deleted(self, obj) -> bool:
        return obj.embedding_id is None and bool(obj.embedding_name)

    def get_connection_name(self, obj) -> str:
        return obj.connection.name if obj.connection_id else "Default provider"

    def get_agent_name(self, obj) -> str:
        if obj.agent_key == "demo":
            return "Demo agent"
        return obj.agent.name if obj.agent else "Deleted agent"


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = [*ConversationSerializer.Meta.fields, "messages"]
