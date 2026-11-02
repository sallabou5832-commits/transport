from django.urls import path
from rest_framework.routers import DefaultRouter

from lien_billetterie.views import (
    AnnulationsDuLienView,
    CleLienViewSet,
    DepartsDuLienView,
    ImportVentesViewSet,
    ReglageBilletterieView,
    VentesDuLienView,
)

router = DefaultRouter()
router.register("lien-billetterie/cles", CleLienViewSet, basename="lien-billetterie-cle")
router.register("lien-billetterie/imports", ImportVentesViewSet, basename="lien-billetterie-import")

urlpatterns = [
    # Réservé au logiciel de billetterie de la compagnie (clé d'API) — voir `lien_billetterie.authentication`.
    path("lien-billetterie/departs/", DepartsDuLienView.as_view(), name="lien-billetterie-departs"),
    path("lien-billetterie/ventes/", VentesDuLienView.as_view(), name="lien-billetterie-ventes"),
    path("lien-billetterie/annulations/", AnnulationsDuLienView.as_view(), name="lien-billetterie-annulations"),
    # Réservé aux agents de la compagnie (voir `lien_billetterie.permissions`).
    path("lien-billetterie/reglage/", ReglageBilletterieView.as_view(), name="lien-billetterie-reglage"),
    *router.urls,
]
