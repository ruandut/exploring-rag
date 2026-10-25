"""Read-side queries for providers. Other apps use these instead of touching models."""

from .crypto import decrypt
from .models import ProviderConfig


def get_provider_config(user) -> ProviderConfig | None:
    return ProviderConfig.objects.filter(owner=user).first()


def get_api_key(config: ProviderConfig) -> str:
    return decrypt(config.api_key_encrypted) if config.api_key_encrypted else ""


def connections_for(user):
    from .models import Connection

    return Connection.objects.filter(owner=user)


def get_connection(user, connection_id: int):
    from .models import Connection

    return Connection.objects.get(owner=user, pk=connection_id)
