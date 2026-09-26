from django.urls import path

from gamification.views import ClassementView, MonEtatView, VueDesAgentsView

urlpatterns = [
    path("gamification/moi/", MonEtatView.as_view(), name="gamification-moi"),
    path("gamification/classement/", ClassementView.as_view(), name="gamification-classement"),
    path("gamification/agents/", VueDesAgentsView.as_view(), name="gamification-agents"),
]
