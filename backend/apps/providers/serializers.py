from rest_framework import serializers

from .models import Connection, ProviderConfig, ProviderKind


def _needs_base_url(serializer, attrs):
    """OpenAI-compatible endpoints need a URL; Anthropic and Google default to their own."""
    kind = attrs.get("kind", getattr(serializer.instance, "kind", ProviderKind.OPENAI))
    url = attrs.get("base_url", getattr(serializer.instance, "base_url", ""))
    if kind == ProviderKind.OPENAI and not url:
        raise serializers.ValidationError(
            {"base_url": "An OpenAI-compatible endpoint needs a base URL."}
        )
    return attrs


class ProviderConfigSerializer(serializers.ModelSerializer):
    # Write-only: the key goes in, only its last 4 characters ever come out (AT-0004-01).
    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=500
    )
    has_api_key = serializers.SerializerMethodField()

    class Meta:
        model = ProviderConfig
        fields = [
            "kind",
            "base_url",
            "api_key",
            "api_key_last4",
            "has_api_key",
            "chat_model",
            "updated_at",
        ]
        read_only_fields = ["api_key_last4", "updated_at"]

    def get_has_api_key(self, obj) -> bool:
        return bool(obj.api_key_encrypted)

    def validate(self, attrs):
        return _needs_base_url(self, attrs)


class TestConnectionSerializer(serializers.Serializer):
    """Values from the (possibly unsaved) form. A blank api_key means "use the saved one"."""

    kind = serializers.ChoiceField(choices=ProviderKind.choices, default=ProviderKind.OPENAI)
    base_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    api_key = serializers.CharField(required=False, allow_blank=True, max_length=500)
    chat_model = serializers.CharField(max_length=200)

    def validate(self, attrs):
        return _needs_base_url(self, attrs)


class ConnectionSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=500
    )
    has_api_key = serializers.SerializerMethodField()

    class Meta:
        model = Connection
        fields = [
            "id",
            "name",
            "kind",
            "base_url",
            "api_key",
            "api_key_last4",
            "has_api_key",
            "updated_at",
        ]
        read_only_fields = ["id", "api_key_last4", "updated_at"]

    def get_has_api_key(self, obj) -> bool:
        return bool(obj.api_key_encrypted)

    def validate_name(self, name):
        owner = self.context["request"].user
        clash = Connection.objects.filter(owner=owner, name=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("You already have a connection with this name.")
        return name

    def validate(self, attrs):
        return _needs_base_url(self, attrs)
