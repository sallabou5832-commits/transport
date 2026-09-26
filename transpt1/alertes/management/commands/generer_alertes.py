from django.core.management.base import BaseCommand

from alertes.generation import generer
from core.models import Company


class Command(BaseCommand):
    help = (
        "Génère les alertes automatiques (seuils critiques, départs à risque, échéances d'assurance) de chaque "
        "compagnie. À planifier toutes les 5 à 10 minutes ; relancer la commande ne crée aucun doublon."
    )

    def handle(self, *args, **options):
        total = 0
        for company in Company.objects.all():
            creees = generer(company)
            total += len(creees)
            for alerte in creees:
                self.stdout.write(f"[{company}] {alerte.titre}")
        self.stdout.write(self.style.SUCCESS(f"{total} alerte(s) créée(s)."))
