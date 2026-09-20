from rest_framework.routers import DefaultRouter

from billetterie.views import DepartViewSet, TicketViewSet

router = DefaultRouter()
router.register("departs", DepartViewSet, basename="depart")
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls
