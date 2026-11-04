from django.urls import path
from rest_framework.routers import DefaultRouter

from configuration.views import (
    CadreCompagnieView,
    CatalogueView,
    ConfigurationAgentViewSet,
    ConfigurationPosteViewSet,
    MaConfigurationView,
    MesPreferencesView,
    ReglementInterieurView,
)

router = DefaultRouter()
router.register("configuration/postes", ConfigurationPosteViewSet, basename="configuration-poste")
router.register("configuration/agents", ConfigurationAgentViewSet, basename="configuration-agent")

urlpatterns = [
    path("configuration/moi/", MaConfigurationView.as_view(), name="configuration-moi"),
    path("configuration/mes-preferences/", MesPreferencesView.as_view(), name="configuration-mes-preferences"),
    path("configuration/catalogue/", CatalogueView.as_view(), name="configuration-catalogue"),
    path("configuration/compagnie/", CadreCompagnieView.as_view(), name="configuration-compagnie"),
    path("configuration/reglement/", ReglementInterieurView.as_view(), name="configuration-reglement"),
    *router.urls,
]
