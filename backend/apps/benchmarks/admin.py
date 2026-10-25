from django.contrib import admin

from .models import BenchmarkRun, CaseResult


class ResultInline(admin.TabularInline):
    model = CaseResult
    extra = 0
    fields = ["position", "status", "passed", "latency_ms", "error"]
    readonly_fields = fields


@admin.register(BenchmarkRun)
class RunAdmin(admin.ModelAdmin):
    list_display = ["__str__", "owner", "status", "created_at"]
    inlines = [ResultInline]
