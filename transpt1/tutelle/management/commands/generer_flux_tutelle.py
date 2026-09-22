from django.core.management.base import BaseCommand

from core.models import Company
from tutelle import generation


class Command(BaseCommand):
    help = (
        "Génère les flux tutelle automatiques (incidents graves, assurances proches de l'échéance) de chaque "
        "compagnie. Les incidents préviennent déjà en temps réel (voir tutelle.signals) ; cette commande rattrape "
        "surtout les assurances (aucun évènement de sauvegarde à écouter pour une échéance qui approche). À "
        "planifier une fois par jour ; relancer ne crée aucun doublon."
    )

    def handle(self, *args, **options):
        total = 0
        for company in Company.objects.all():
            crees = generation.generer_tout(company)
            for flux in crees["securite"] + crees["conformite"]:
                self.stdout.write(f"[{company}] {flux}")
            total += len(crees["securite"]) + len(crees["conformite"])
        self.stdout.write(self.style.SUCCESS(f"{total} flux tutelle créé(s)."))
