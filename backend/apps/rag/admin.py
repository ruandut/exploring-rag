from django.contrib import admin

from .models import EmbeddingIndex, IndexedDocument


@admin.register(EmbeddingIndex)
class EmbeddingIndexAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "model", "dimensions", "strategy", "chunk_size", "status"]
    list_filter = ["status", "strategy"]


@admin.register(IndexedDocument)
class IndexedDocumentAdmin(admin.ModelAdmin):
    list_display = ["index", "document", "status", "chunk_count", "indexed_at"]
    list_filter = ["status"]
