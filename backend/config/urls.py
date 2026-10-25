from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/jobs/", include("apps.jobs.urls")),
    path("api/providers/", include("apps.providers.urls")),
    path("api/library/", include("apps.library.urls")),
    path("api/agents/", include("apps.agents.urls")),
    path("api/chat/", include("apps.chat.urls")),
    path("api/evals/", include("apps.evals.urls")),
    path("api/benchmarks/", include("apps.benchmarks.urls")),
    path("api/rag/", include("apps.rag.urls")),
]
