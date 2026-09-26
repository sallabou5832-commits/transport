from rest_framework.routers import DefaultRouter

from investissements.views import InvestissementViewSet

router = DefaultRouter()
router.register("investissements", InvestissementViewSet, basename="investissement")

urlpatterns = router.urls
