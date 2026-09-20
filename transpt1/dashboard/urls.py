from django.urls import path

from dashboard.views import (
    DashboardDirectionView,
    DashboardExploitationView,
    DashboardPlateformeView,
    DashboardQhseView,
)

urlpatterns = [
    path("dashboard/direction/", DashboardDirectionView.as_view(), name="dashboard-direction"),
    path("dashboard/qhse/", DashboardQhseView.as_view(), name="dashboard-qhse"),
    path(
        "dashboard/exploitation/", DashboardExploitationView.as_view(), name="dashboard-exploitation"
    ),
    path("dashboard/plateforme/", DashboardPlateformeView.as_view(), name="dashboard-plateforme"),
]
