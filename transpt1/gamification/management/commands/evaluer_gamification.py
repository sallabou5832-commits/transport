from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Role
from gamification.moteur import etat_agent


class Command(BaseCommand):
    help = (
        "Évalue les missions du jour et les badges de tous les agents dont le poste affiche la gamification, et enregistre "
        "ce qui a été accompli (même si l'agent n'a pas ouvert l'application). À planifier chaque soir ; rejouable sans doublon."
    )

    def handle(self, *args, **options):
        missions = badges = agents = 0
        for agent in get_user_model().objects.exclude(role=Role.SUPERADMIN).select_related("company"):
            etat = etat_agent(agent)
            if not etat["actif"]:
                continue
            agents += 1
            missions += len(etat["nouvelles"]["missions"])
            badges += len(etat["nouvelles"]["badges"])
        self.stdout.write(self.style.SUCCESS(f"{agents} agent(s) évalué(s) : {missions} mission(s) et {badges} badge(s) enregistré(s)."))
