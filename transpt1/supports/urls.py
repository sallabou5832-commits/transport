from django.urls import path
from rest_framework.routers import DefaultRouter

from supports.views import (
    AssuranceViewSet,
    ConformiteView,
    DossierAgentViewSet,
    ModeleJuridiqueViewSet,
    PieceSinistreViewSet,
    ReportingJuridiqueView,
    SinistreViewSet,
    SyntheseFinanciereView,
)

router = DefaultRouter()
router.register("dossiers-agents", DossierAgentViewSet, basename="dossier-agent")
router.register("assurances", AssuranceViewSet, basename="assurance")
router.register("sinistres", SinistreViewSet, basename="sinistre")
router.register("pieces-sinistre", PieceSinistreViewSet, basename="piece-sinistre")
router.register("modeles-juridiques", ModeleJuridiqueViewSet, basename="modele-juridique")

urlpatterns = [
    path("synthese-financiere/", SyntheseFinanciereView.as_view(), name="synthese-financiere"),
    path("conformite/", ConformiteView.as_view(), name="conformite"),
    path("juridique/reporting/", ReportingJuridiqueView.as_view(), name="juridique-reporting"),
] + router.urls
