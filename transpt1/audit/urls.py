from django.urls import path

from audit.views import JournalAuditView

urlpatterns = [
    path("audit/", JournalAuditView.as_view(), name="journal-audit"),
]
