from django.contrib import admin

from .models import IndexingConfig


@admin.register(IndexingConfig)
class IndexingConfigAdmin(admin.ModelAdmin):
    list_display = ["owner", "strategy", "chunk_size", "chunk_overlap", "updated_at"]
