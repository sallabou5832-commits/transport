from django.urls import path
from rest_framework.routers import DefaultRouter

from communication.views import (
    CatalogueCommunicationView,
    DocumentArchiveViewSet,
    EvenementAgendaViewSet,
    GuidesView,
    MessageDirectViewSet,
    NoteServiceViewSet,
)

router = DefaultRouter()
router.register("notes-service", NoteServiceViewSet, basename="note-service")
router.register("messages-directs", MessageDirectViewSet, basename="message-direct")
router.register("agenda", EvenementAgendaViewSet, basename="agenda")
router.register("archives", DocumentArchiveViewSet, basename="archive")

urlpatterns = [
    path("communication/catalogue/", CatalogueCommunicationView.as_view(), name="communication-catalogue"),
    path("guides/", GuidesView.as_view(), name="guides"),
    *router.urls,
]
