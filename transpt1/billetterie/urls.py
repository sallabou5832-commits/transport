from rest_framework.routers import DefaultRouter

from billetterie.views import ClotureCaisseViewSet, DepartViewSet, TicketViewSet

router = DefaultRouter()
router.register("departs", DepartViewSet, basename="depart")
router.register("tickets", TicketViewSet, basename="ticket")
router.register("clotures-caisse", ClotureCaisseViewSet, basename="cloture-caisse")

urlpatterns = router.urls
