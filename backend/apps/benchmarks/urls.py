from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import RunViewSet, model_speed

router = SimpleRouter()
router.register("runs", RunViewSet, basename="benchmark-run")

urlpatterns = [path("speed/", model_speed, name="benchmark-speed"), *router.urls]
