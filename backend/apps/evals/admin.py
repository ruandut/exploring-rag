from django.contrib import admin

from .models import Boundary, EvalCase, EvalSuite


class CaseInline(admin.TabularInline):
    model = EvalCase
    extra = 0


class BoundaryInline(admin.TabularInline):
    model = Boundary
    extra = 0


@admin.register(EvalSuite)
class SuiteAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "version", "updated_at"]
    inlines = [CaseInline, BoundaryInline]
