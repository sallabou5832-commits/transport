import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.demo_garde import refuser_hors_developpement
from core.models import Company
from reseau.models import ClasseVehicule, Gare, Ligne, Quai, Vehicule, VehiculeStatut


class Command(BaseCommand):
    help = (
        "Cree des gares, lignes et vehicules de demonstration pour les compagnies "
        "creees par seed_demo_users (a lancer avant celle-ci)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        refuser_hors_developpement("seed_demo_reseau")
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

        # Fiches (coordonnées, horaires, quais, distances, véhicules) : valeurs plausibles, reprises seulement à la création.
        gare_adjame = self._create_gare(
            "Gare Adjamé", "Abidjan", stc, chef_stc, adresse="Adjamé, boulevard Nangui Abrogoua", telephone="0707070701",
            heure_ouverture=datetime.time(5, 0), heure_fermeture=datetime.time(22, 0),
        )
        gare_bouake_stc = self._create_gare("Gare Bouaké", "Bouaké", stc, None, telephone="0707070702")
        self._create_quais(gare_adjame, ["Quai 1", "Quai 2", "Quai 3"])
        self._create_quais(gare_bouake_stc, ["Quai 1"])
        self._create_ligne("Abidjan-Bouaké", gare_adjame, gare_bouake_stc, stc, distance_km=350, duree_prevue_minutes=330)
        self._create_vehicule(
            "CI-1001-AB", 70, VehiculeStatut.DISPONIBLE, stc, gare_adjame, marque="Higer", modele="KLQ6129",
            annee_mise_en_circulation=2018, classe=ClasseVehicule.CLIMATISE,
        )
        self._create_vehicule(
            "CI-1002-AB", 30, VehiculeStatut.EN_LIGNE, stc, gare_bouake_stc, marque="Toyota", modele="Coaster",
            annee_mise_en_circulation=2015, classe=ClasseVehicule.STANDARD,
        )

        gare_bouake_savane = self._create_gare("Gare Bouaké Nord", "Bouaké", savane, chef_savane, telephone="0505050501")
        gare_korhogo = self._create_gare("Gare Korhogo", "Korhogo", savane, None)
        self._create_quais(gare_bouake_savane, ["A", "B"])
        self._create_ligne("Bouaké-Korhogo", gare_bouake_savane, gare_korhogo, savane, distance_km=230, duree_prevue_minutes=210)
        self._create_vehicule(
            "CI-2001-CD", 50, VehiculeStatut.EN_MAINTENANCE, savane, gare_bouake_savane, marque="Yutong",
            annee_mise_en_circulation=2012,
        )

    def _create_gare(self, nom, ville, company, chef, **fiche):
        gare, created = Gare.objects.get_or_create(
            nom=nom, company=company, defaults={"ville": ville, "chef": chef, **fiche}
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Créée' if created else 'Existe déjà'} : {gare}")
        )
        return gare

    def _create_quais(self, gare, noms):
        for nom in noms:
            Quai.objects.get_or_create(gare=gare, nom=nom, defaults={"company": gare.company})

    def _create_ligne(self, nom, gare_depart, gare_arrivee, company, **fiche):
        ligne, created = Ligne.objects.get_or_create(
            nom=nom,
            company=company,
            defaults={"gare_depart": gare_depart, "gare_arrivee": gare_arrivee, **fiche},
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Créée' if created else 'Existe déjà'} : {ligne}")
        )
        return ligne

    def _create_vehicule(self, immatriculation, capacite, statut, company, gare=None, **fiche):
        vehicule, created = Vehicule.objects.get_or_create(
            immatriculation=immatriculation,
            defaults={"capacite": capacite, "statut": statut, "company": company, "gare": gare, **fiche},
        )
        if not created and vehicule.gare_id is None and gare is not None:
            vehicule.gare = gare  # un parc déjà en base est rattaché à sa gare sans rien recréer
            vehicule.save(update_fields=["gare"])
        self.stdout.write(
            self.style.SUCCESS(f"{'Créé' if created else 'Existe déjà'} : {vehicule}")
        )
        return vehicule
