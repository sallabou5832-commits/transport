import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import sauvegarde


class Command(BaseCommand):
    help = (
        "Prouve qu'une sauvegarde est utilisable : empreinte, lecture de l'archive, puis restauration complète dans "
        "une base temporaire (supprimée ensuite). Sans argument, prend la plus récente. À lancer chaque semaine."
    )

    def add_arguments(self, parser):
        parser.add_argument("fichier", nargs="?", help="Sauvegarde à vérifier (défaut : la plus récente).")
        parser.add_argument("--dossier", default=settings.BACKUP_DIR)

    def handle(self, *args, **options):
        fichier = options["fichier"]
        if not fichier:
            recentes = sauvegarde.sauvegardes(options["dossier"]) if os.path.isdir(options["dossier"]) else []
            if not recentes:
                raise CommandError(f"Aucune sauvegarde dans {options['dossier']}.")
            fichier = recentes[0]
        try:
            resultat = sauvegarde.verifier(
                fichier,
                admin_utilisateur=os.environ.get("SAUVEGARDE_ADMIN_USER"),
                admin_mot_de_passe=os.environ.get("SAUVEGARDE_ADMIN_PASSWORD"),
            )
        except sauvegarde.SauvegardeErreur as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{resultat['fichier']} : restauration réussie ({resultat['tables']} tables, "
                f"{resultat['migrations']} migrations). Base temporaire supprimée."
            )
        )
