from rest_framework.routers import SimpleRouter

from .views import RunViewSet

router = SimpleRouter()
router.register("runs", RunViewSet, basename="benchmark-run")

urlpatterns = router.urls
