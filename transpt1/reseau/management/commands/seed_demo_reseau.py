from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Company
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


class Command(BaseCommand):
    help = (
        "Cree des gares, lignes et vehicules de demonstration pour les compagnies "
        "creees par seed_demo_users (a lancer avant celle-ci)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        try:
            stc = Company.objects.get(name="STC Voyages")
            savane = Company.objects.get(name="Express Savane")
        except Company.DoesNotExist as exc:
            raise CommandError(
                "Compagnies de demo introuvables. Lancez d'abord : "
                "python manage.py seed_demo_users"
            ) from exc

        chef_stc = User.objects.filter(username="chef_gare_stc").first()
        chef_savane = User.objects.filter(username="chef_gare_savane").first()

        gare_adjame = self._create_gare("Gare Adjamé", "Abidjan", stc, chef_stc)
        gare_bouake_stc = self._create_gare("Gare Bouaké", "Bouaké", stc, None)
        self._create_ligne("Abidjan-Bouaké", gare_adjame, gare_bouake_stc, stc)
        self._create_vehicule("CI-1001-AB", 70, VehiculeStatut.DISPONIBLE, stc)
        self._create_vehicule("CI-1002-AB", 30, VehiculeStatut.EN_LIGNE, stc)

        gare_bouake_savane = self._create_gare("Gare Bouaké Nord", "Bouaké", savane, chef_savane)
        gare_korhogo = self._create_gare("Gare Korhogo", "Korhogo", savane, None)
        self._create_ligne("Bouaké-Korhogo", gare_bouake_savane, gare_korhogo, savane)
        self._create_vehicule("CI-2001-CD", 50, VehiculeStatut.EN_MAINTENANCE, savane)

    def _create_gare(self, nom, ville, company, chef):
        gare, created = Gare.objects.get_or_create(
            nom=nom, company=company, defaults={"ville": ville, "chef": chef}
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Créée' if created else 'Existe déjà'} : {gare}")
        )
        return gare

    def _create_ligne(self, nom, gare_depart, gare_arrivee, company):
        ligne, created = Ligne.objects.get_or_create(
            nom=nom,
            company=company,
            defaults={"gare_depart": gare_depart, "gare_arrivee": gare_arrivee},
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Créée' if created else 'Existe déjà'} : {ligne}")
        )
        return ligne

    def _create_vehicule(self, immatriculation, capacite, statut, company):
        vehicule, created = Vehicule.objects.get_or_create(
            immatriculation=immatriculation,
            defaults={"capacite": capacite, "statut": statut, "company": company},
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Créé' if created else 'Existe déjà'} : {vehicule}")
        )
        return vehicule
