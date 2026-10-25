from django.contrib import admin

from .models import Document, Folder


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "parent", "created_at"]
    list_filter = ["owner"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "folder", "status", "chunk_count", "size", "updated_at"]
    list_filter = ["status", "owner"]
    readonly_fields = ["status", "error", "chunk_count", "indexed_at"]
