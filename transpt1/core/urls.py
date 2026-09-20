from django.urls import path

from core.views import CompanyDetailView, MeView

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="me"),
    path("companies/<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
]
