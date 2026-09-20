from django.urls import path
from rest_framework.routers import DefaultRouter

from supports.views import (
    AssuranceViewSet,
    DossierAgentViewSet,
    SinistreViewSet,
    SyntheseFinanciereView,
)

router = DefaultRouter()
router.register("dossiers-agents", DossierAgentViewSet, basename="dossier-agent")
router.register("assurances", AssuranceViewSet, basename="assurance")
router.register("sinistres", SinistreViewSet, basename="sinistre")

urlpatterns = [
    path("synthese-financiere/", SyntheseFinanciereView.as_view(), name="synthese-financiere"),
] + router.urls
