from rest_framework.routers import DefaultRouter

from reseau.views import GareViewSet, LigneViewSet, VehiculeViewSet

router = DefaultRouter()
router.register("gares", GareViewSet, basename="gare")
router.register("lignes", LigneViewSet, basename="ligne")
router.register("vehicules", VehiculeViewSet, basename="vehicule")

urlpatterns = router.urls
