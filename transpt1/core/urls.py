from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views import (
    ChangementMotDePasseView,
    CompanyDetailView,
    ComptesViewSet,
    FermetureAutresSessionsView,
    LogoCompagnieView,
    MaCompagnieView,
    MeView,
    RetraitLogoCompagnieView,
)

router = DefaultRouter()
router.register("comptes", ComptesViewSet, basename="compte")

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/mot-de-passe/", ChangementMotDePasseView.as_view(), name="mot-de-passe"),
    path("auth/fermer-autres-sessions/", FermetureAutresSessionsView.as_view(), name="fermer-autres-sessions"),
    path("companies/<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
    path("compagnie/", MaCompagnieView.as_view(), name="ma-compagnie"),
    path("compagnie/logo/", LogoCompagnieView.as_view(), name="logo-compagnie"),
    path("compagnie/logo/retirer/", RetraitLogoCompagnieView.as_view(), name="retrait-logo-compagnie"),
    *router.urls,
]
