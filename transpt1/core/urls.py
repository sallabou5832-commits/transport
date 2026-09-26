from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views import CompanyDetailView, ComptesViewSet, MeView

router = DefaultRouter()
router.register("comptes", ComptesViewSet, basename="compte")

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="me"),
    path("companies/<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
    *router.urls,
]
