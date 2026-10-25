from rest_framework.routers import SimpleRouter

from .views import DocumentViewSet, FolderViewSet

router = SimpleRouter()
router.register("folders", FolderViewSet, basename="folder")
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = router.urls
