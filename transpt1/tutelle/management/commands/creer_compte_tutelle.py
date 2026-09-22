from django.core.management.base import BaseCommand, CommandError

from tutelle.models import CompteTutelle


class Command(BaseCommand):
    help = (
        "Crée un compte tutelle (Ministère des Transports, OSER, AMUGA, OFT...) et affiche sa clé d'API en clair : "
        "elle n'est jamais stockée telle quelle, retenez-la maintenant, elle ne sera plus jamais affichée."
    )

    def add_arguments(self, parser):
        parser.add_argument("nom", help="Nom du compte, par exemple « Ministère des Transports » ou « OSER ».")

    def handle(self, *args, **options):
        nom = options["nom"].strip()
        if not nom:
            raise CommandError("Indiquez un nom.")
        compte, cle_en_clair = CompteTutelle.creer(nom)
        self.stdout.write(self.style.SUCCESS(f"Compte tutelle « {compte.nom} » créé (id {compte.pk})."))
        self.stdout.write(f"Clé d'API : {cle_en_clair}")
        self.stdout.write("À utiliser dans l'en-tête « Authorization: ApiKey <clé> ». Conservez-la en lieu sûr.")
