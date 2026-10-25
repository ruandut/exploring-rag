from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("embeddings", views.EmbeddingViewSet, basename="embedding")

urlpatterns = [
    path("documents/<int:document_id>/chunks/", views.document_chunks, name="document_chunks"),
    *router.urls,
]
