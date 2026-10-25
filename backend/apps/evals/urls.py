from rest_framework.routers import SimpleRouter

from .views import SuiteViewSet

router = SimpleRouter()
router.register("suites", SuiteViewSet, basename="suite")

urlpatterns = router.urls
