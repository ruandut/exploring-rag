from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "status", "run_id", "metadata", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    agent_name = serializers.SerializerMethodField()
    message_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Conversation
        fields = ["id", "title", "agent_key", "agent_name", "message_count", "updated_at"]

    def get_agent_name(self, obj) -> str:
        if obj.agent_key == "demo":
            return "Demo agent"
        return obj.agent.name if obj.agent else "Deleted agent"


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = [*ConversationSerializer.Meta.fields, "messages"]
