from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import sauvegarde


class Command(BaseCommand):
    help = (
        "Sort en erreur (code 1) si la dernière sauvegarde a échoué ou date de trop longtemps : à brancher sur la "
        "surveillance (cron, Uptime Kuma, Nagios…). Une sauvegarde qui échoue en silence est pire qu'aucune."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dossier", default=settings.BACKUP_DIR)
        parser.add_argument("--max-heures", type=int, default=settings.BACKUP_MAX_AGE_HOURS)

    def handle(self, *args, **options):
        ok, message = sauvegarde.etat(options["dossier"], options["max_heures"])
        if not ok:
            raise CommandError(message)
        self.stdout.write(self.style.SUCCESS(message))
