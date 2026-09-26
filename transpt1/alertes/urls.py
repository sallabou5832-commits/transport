from rest_framework.routers import DefaultRouter

from alertes.views import AlerteViewSet

router = DefaultRouter()
router.register("alertes", AlerteViewSet, basename="alerte")

urlpatterns = router.urls
