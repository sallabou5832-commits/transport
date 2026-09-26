from rest_framework.routers import DefaultRouter

from reseau.views import AffectationGareViewSet, ChangementLigneViewSet, GareViewSet, LigneViewSet, VehiculeViewSet

router = DefaultRouter()
router.register("gares", GareViewSet, basename="gare")
router.register("lignes", LigneViewSet, basename="ligne")
router.register("vehicules", VehiculeViewSet, basename="vehicule")
router.register("changements-ligne", ChangementLigneViewSet, basename="changement-ligne")
router.register("affectations-gare", AffectationGareViewSet, basename="affectation-gare")

urlpatterns = router.urls
