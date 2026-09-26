import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from billetterie.caisse import cloturer
from billetterie.models import StatutTicket, Ticket
from configuration.regles import NiveauAutomatisation
from configuration.services import configuration_effective
from core.models import Role


class Command(BaseCommand):
    help = (
        "Clôture automatiquement les caisses des guichetiers dont le niveau d'automatisation est « automatique » et qui "
        "ont vendu des tickets ce jour sans avoir clôturé. À planifier en fin de journée (voir DEPLOIEMENT.md) ; "
        "relancer la commande ne clôture rien deux fois."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Jour à clôturer (AAAA-MM-JJ) ; aujourd'hui par défaut.")

    def handle(self, *args, **options):
        jour = datetime.date.fromisoformat(options["date"]) if options["date"] else timezone.localdate()
        vendeurs = (
            Ticket.objects.filter(date_vente__date=jour, statut=StatutTicket.VALIDE)
            .values_list("vendu_par", flat=True)
            .distinct()
        )
        faites = 0
        for guichetier in get_user_model().objects.filter(pk__in=vendeurs, role=Role.GUICHETIER):
            if configuration_effective(guichetier)["niveau_automatisation"] != NiveauAutomatisation.AUTOMATIQUE:
                continue
            _, creee = cloturer(guichetier, jour, automatique=True)
            if creee:
                faites += 1
                self.stdout.write(f"Caisse clôturée : {guichetier.username} ({jour})")
        self.stdout.write(self.style.SUCCESS(f"{faites} caisse(s) clôturée(s) automatiquement."))
