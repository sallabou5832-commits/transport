from django.urls import path

from formation.views import DemarrerParcoursView, MonParcoursView, TerminerEtapeView

urlpatterns = [
    path("formation/mon-parcours/", MonParcoursView.as_view(), name="formation-mon-parcours"),
    path(
        "formation/mon-parcours/demarrer/",
        DemarrerParcoursView.as_view(),
        name="formation-demarrer",
    ),
    path(
        "formation/mon-parcours/etapes/<int:etape_id>/terminer/",
        TerminerEtapeView.as_view(),
        name="formation-terminer-etape",
    ),
]
