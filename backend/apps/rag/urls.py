from django.urls import path

from . import views

urlpatterns = [
    path("indexing-config/", views.indexing_config, name="indexing_config"),
    path("documents/<int:document_id>/chunks/", views.document_chunks, name="document_chunks"),
]
