from django.core.management.base import BaseCommand

from formation.parcours_de_base import charger_parcours_de_base


class Command(BaseCommand):
    help = (
        "Crée les parcours de formation de base (guichetier, chauffeur principal, magasinier). "
        "Un parcours déjà présent est laissé intact, sauf avec --force."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Réécrit le contenu des parcours de base déjà présents (écrase les modifications).",
        )

    def handle(self, *args, **options):
        crees, ignores = charger_parcours_de_base(force=options["force"])
        for role in crees:
            self.stdout.write(self.style.SUCCESS(f"Parcours créé ou mis à jour : {role}"))
        for role in ignores:
            self.stdout.write(f"Parcours déjà présent, laissé intact : {role} (utilisez --force pour le réécrire)")
