from django.core.management.base import BaseCommand

from personnel_roulant import suivi


class Command(BaseCommand):
    help = (
        "Supprime les relevés GPS (PositionVehicule) plus vieux que POSITIONS_RETENTION_JOURS (30 jours par défaut) : "
        "rien ne les exploite au-delà de la dernière position de chaque trajet (la carte, la fatigue). Sans purge, la "
        "table ne fait que grossir et ralentit la carte temps réel. À planifier chaque nuit (voir DEPLOIEMENT.md) ; "
        "relancer ne fait jamais de mal (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--jours", type=int, default=None, help="Remplace POSITIONS_RETENTION_JOURS pour cet appel seulement."
        )

    def handle(self, *args, **options):
        total = suivi.purger_positions(retention_jours=options["jours"])
        self.stdout.write(self.style.SUCCESS(f"{total} relevé(s) GPS supprimé(s)."))
