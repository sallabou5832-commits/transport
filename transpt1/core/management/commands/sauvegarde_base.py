from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import sauvegarde


class Command(BaseCommand):
    help = (
        "Sauvegarde la base PostgreSQL (pg_dump), contrôle l'archive, écrit son empreinte SHA-256, supprime les "
        "sauvegardes trop anciennes et, si demandé, envoie le fichier hors du serveur. À planifier chaque nuit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dossier", default=settings.BACKUP_DIR, help="Dossier des sauvegardes.")
        parser.add_argument("--garder-jours", type=int, default=settings.BACKUP_RETENTION_DAYS)
        parser.add_argument(
            "--garder-minimum",
            type=int,
            default=settings.BACKUP_MIN_KEEP,
            help="Nombre de sauvegardes conservées quel que soit leur âge.",
        )
        parser.add_argument(
            "--commande-apres",
            default=settings.BACKUP_POST_COMMAND,
            help="Commande lancée avec le chemin du fichier en dernier argument (envoi hors du serveur).",
        )
        parser.add_argument(
            "--verifier",
            action="store_true",
            help="Restaure aussitôt la sauvegarde dans une base temporaire pour prouver qu'elle est utilisable.",
        )

    def handle(self, *args, **options):
        try:
            statut = sauvegarde.sauvegarder(
                options["dossier"],
                garder_jours=options["garder_jours"],
                garder_minimum=options["garder_minimum"],
                commande_apres=options["commande_apres"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sauvegarde {statut['fichier']} : {statut['taille_octets'] / 1024:.0f} Ko en {statut['duree_secondes']} s."
                )
            )
            if statut["supprimees"]:
                self.stdout.write(f"Anciennes sauvegardes supprimées : {', '.join(statut['supprimees'])}")
            if options["verifier"]:
                resultat = sauvegarde.verifier(f"{options['dossier']}/{statut['fichier']}")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Restauration de test réussie : {resultat['tables']} tables, {resultat['migrations']} migrations."
                    )
                )
        except sauvegarde.SauvegardeErreur as exc:
            raise CommandError(str(exc)) from exc
