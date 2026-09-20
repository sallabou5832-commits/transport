from django.urls import path

from dashboard.views import DashboardDirectionView, DashboardQhseView

urlpatterns = [
    path("dashboard/direction/", DashboardDirectionView.as_view(), name="dashboard-direction"),
    path("dashboard/qhse/", DashboardQhseView.as_view(), name="dashboard-qhse"),
]
