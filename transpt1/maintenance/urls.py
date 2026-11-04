from django.urls import path
from rest_framework.routers import DefaultRouter

from maintenance.views import (
    BesoinRenouvellementView,
    ChargeMecaniciensView,
    DemandePieceViewSet,
    EntreePieceViewSet,
    FicheVehiculeView,
    IntervenantsView,
    InventairePieceViewSet,
    OrdreReparationViewSet,
    PieceViewSet,
    PlanEntretienViewSet,
    SortiePieceViewSet,
)

router = DefaultRouter()
router.register("pieces", PieceViewSet, basename="piece")
router.register("ordres-reparation", OrdreReparationViewSet, basename="ordre-reparation")
router.register("sorties-pieces", SortiePieceViewSet, basename="sortie-piece")
router.register("plans-entretien", PlanEntretienViewSet, basename="plan-entretien")
router.register("demandes-pieces", DemandePieceViewSet, basename="demande-piece")
router.register("entrees-pieces", EntreePieceViewSet, basename="entree-piece")
router.register("inventaires-pieces", InventairePieceViewSet, basename="inventaire-piece")

urlpatterns = [
    path("fiche-vehicule/<int:pk>/", FicheVehiculeView.as_view(), name="fiche-vehicule"),
    path("maintenance/charge-mecaniciens/", ChargeMecaniciensView.as_view(), name="charge-mecaniciens"),
    path("maintenance/intervenants/", IntervenantsView.as_view(), name="intervenants"),
    path("maintenance/besoin-renouvellement/", BesoinRenouvellementView.as_view(), name="besoin-renouvellement"),
    *router.urls,
]
