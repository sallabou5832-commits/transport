from django.urls import path
from rest_framework.routers import DefaultRouter

from tutelle.views import FluxEntrantView, FluxTutelleViewSet, GenererFluxView

router = DefaultRouter()
router.register("flux-tutelle", FluxTutelleViewSet, basename="flux-tutelle")

urlpatterns = [
    # Réservé aux comptes tutelle (clé d'API) — voir `tutelle.authentication`.
    path("tutelle/entrant/", FluxEntrantView.as_view(), name="tutelle-entrant"),
    # Réservé au QHSE et au responsable juridique de la compagnie.
    path("tutelle/generer/", GenererFluxView.as_view(), name="tutelle-generer"),
    *router.urls,
]
