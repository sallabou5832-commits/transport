from django.urls import path
from rest_framework.routers import DefaultRouter

from personnel_roulant.views import (
    BlocageSecuriteViewSet,
    ChecklistDepartViewSet,
    ControleLigneViewSet,
    FeuilleDeRouteViewSet,
    IncidentViewSet,
    CarnetDeRouteView,
    MonTrajetView,
    PositionViewSet,
    RelaisViewSet,
)

router = DefaultRouter()
router.register("feuilles-de-route", FeuilleDeRouteViewSet, basename="feuille-de-route")
router.register("checklists", ChecklistDepartViewSet, basename="checklist")
router.register("incidents", IncidentViewSet, basename="incident")
router.register("blocages-securite", BlocageSecuriteViewSet, basename="blocage-securite")
router.register("positions", PositionViewSet, basename="position")
router.register("controles", ControleLigneViewSet, basename="controle")
router.register("relais", RelaisViewSet, basename="relais")

urlpatterns = [
    path("suivi/moi/", MonTrajetView.as_view(), name="suivi-moi"),
    path("carnet-de-route/", CarnetDeRouteView.as_view(), name="carnet-de-route"),
    *router.urls,
]
