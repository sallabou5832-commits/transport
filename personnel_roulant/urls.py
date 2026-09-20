from rest_framework.routers import DefaultRouter

from personnel_roulant.views import ChecklistDepartViewSet, FeuilleDeRouteViewSet, IncidentViewSet

router = DefaultRouter()
router.register("feuilles-de-route", FeuilleDeRouteViewSet, basename="feuille-de-route")
router.register("checklists", ChecklistDepartViewSet, basename="checklist")
router.register("incidents", IncidentViewSet, basename="incident")

urlpatterns = router.urls
