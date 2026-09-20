from rest_framework.routers import DefaultRouter

from maintenance.views import OrdreReparationViewSet, PieceViewSet, SortiePieceViewSet

router = DefaultRouter()
router.register("pieces", PieceViewSet, basename="piece")
router.register("ordres-reparation", OrdreReparationViewSet, basename="ordre-reparation")
router.register("sorties-pieces", SortiePieceViewSet, basename="sortie-piece")

urlpatterns = router.urls
