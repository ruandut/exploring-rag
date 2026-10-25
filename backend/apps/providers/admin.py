from django.contrib import admin

from .models import Connection, ProviderConfig


@admin.register(ProviderConfig)
class ProviderConfigAdmin(admin.ModelAdmin):
    list_display = ["owner", "base_url", "chat_model", "updated_at"]
    # The encrypted key is never shown, even to admins.
    exclude = ["api_key_encrypted"]
    readonly_fields = ["api_key_last4"]


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "base_url", "updated_at"]
    exclude = ["api_key_encrypted"]
    readonly_fields = ["api_key_last4"]
