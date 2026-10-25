from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("connections", views.ConnectionViewSet, basename="connection")

urlpatterns = [
    path("config/", views.provider_config, name="provider_config"),
    path("test/", views.test_connection, name="provider_test"),
    path("models/", views.default_models, name="provider_models"),
    *router.urls,
]
