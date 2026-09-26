from django.urls import path
from rest_framework.routers import DefaultRouter

from maintenance.views import (
    BesoinRenouvellementView,
    ChargeMecaniciensView,
    DemandePieceViewSet,
    FicheVehiculeView,
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

urlpatterns = [
    path("fiche-vehicule/<int:pk>/", FicheVehiculeView.as_view(), name="fiche-vehicule"),
    path("maintenance/charge-mecaniciens/", ChargeMecaniciensView.as_view(), name="charge-mecaniciens"),
    path("maintenance/besoin-renouvellement/", BesoinRenouvellementView.as_view(), name="besoin-renouvellement"),
    *router.urls,
]
