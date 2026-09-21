import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.demo_garde import refuser_hors_developpement
from core.models import Company, Role

DEMO_PASSWORD = "Demo!2024"

COMPANIES = {
    "stc_voyages": {
        "name": "STC Voyages",
        "headquarters_city": "Abidjan",
        "created_at": datetime.date(2005, 3, 1),
    },
    "express_savane": {
        "name": "Express Savane",
        "headquarters_city": "Bouaké",
        "created_at": datetime.date(2011, 9, 15),
    },
}

# Un compte par rôle du cahier des charges (17 rôles métier + superadmin), pour que chaque tableau
# de bord puisse être essayé. `nom` : « Prénom Nom », affiché dans les tableaux de bord.
DEMO_USERS = [
    {"username": "pdg_stc", "role": Role.PDG, "company": "stc_voyages", "nom": "Marie Koffi"},
    {"username": "secretaire_general_stc", "role": Role.SECRETAIRE_GENERAL, "company": "stc_voyages", "nom": "Paul Aka"},
    {"username": "qhse_stc", "role": Role.QHSE, "company": "stc_voyages", "nom": "Fatou Traore"},
    {"username": "directeur_exploitation_stc", "role": Role.DIRECTEUR_EXPLOITATION, "company": "stc_voyages", "nom": "Yves Bamba"},
    {"username": "chef_gare_stc", "role": Role.CHEF_GARE, "company": "stc_voyages", "nom": "Ali Ouattara"},
    {"username": "chef_ligne_stc", "role": Role.CHEF_LIGNE, "company": "stc_voyages", "nom": "Sita Coulibaly"},
    {"username": "guichetier_stc", "role": Role.GUICHETIER, "company": "stc_voyages", "nom": "Rose Kouame"},
    {"username": "bagagiste_stc", "role": Role.BAGAGISTE, "company": "stc_voyages", "nom": "Issa Kone"},
    {"username": "chauffeur_stc", "role": Role.CHAUFFEUR_PRINCIPAL, "company": "stc_voyages", "nom": "Awa Kone"},
    {"username": "chauffeur2_stc", "role": Role.CHAUFFEUR_PRINCIPAL, "company": "stc_voyages", "nom": "Moussa Diallo"},
    {"username": "chauffeur3_stc", "role": Role.CHAUFFEUR_PRINCIPAL, "company": "stc_voyages", "nom": "Adama Traore"},
    {"username": "chauffeur_relais_stc", "role": Role.CHAUFFEUR_RELAIS, "company": "stc_voyages", "nom": "Ibrahim Sanogo"},
    {"username": "controleur_stc", "role": Role.CONTROLEUR_LIGNE, "company": "stc_voyages", "nom": "Jean Yao"},
    {"username": "directeur_technique_stc", "role": Role.DIRECTEUR_TECHNIQUE, "company": "stc_voyages", "nom": "Hamed Sylla"},
    {"username": "magasinier_stc", "role": Role.MAGASINIER, "company": "stc_voyages", "nom": "Kader Doumbia"},
    {"username": "chef_atelier_stc", "role": Role.CHEF_ATELIER, "company": "stc_voyages", "nom": "Boubacar Camara"},
    {"username": "drh_stc", "role": Role.DRH, "company": "stc_voyages", "nom": "Nadege Kouassi"},
    {"username": "directeur_financier_stc", "role": Role.DIRECTEUR_FINANCIER, "company": "stc_voyages", "nom": "Serge N'Guessan"},
    {"username": "responsable_juridique_stc", "role": Role.RESPONSABLE_JURIDIQUE, "company": "stc_voyages", "nom": "Aicha Diomande"},
    {"username": "pdg_savane", "role": Role.PDG, "company": "express_savane", "nom": "Lucien Soro"},
    {"username": "chef_gare_savane", "role": Role.CHEF_GARE, "company": "express_savane", "nom": "Mariam Toure"},
    {"username": "chauffeur_savane", "role": Role.CHAUFFEUR_PRINCIPAL, "company": "express_savane", "nom": "Sekou Fofana"},
    {"username": "guichetier_savane", "role": Role.GUICHETIER, "company": "express_savane", "nom": "Djeneba Cisse"},
    {"username": "superadmin_demo", "role": Role.SUPERADMIN, "company": None, "nom": "Opérateur Plateforme"},
]


class Command(BaseCommand):
    help = "Crée des compagnies et utilisateurs de démonstration pour les tests manuels."

    @transaction.atomic
    def handle(self, *args, **options):
        refuser_hors_developpement("seed_demo_users")
        User = get_user_model()

        companies = {}
        for key, data in COMPANIES.items():
            company, created = Company.objects.get_or_create(name=data["name"], defaults=data)
            companies[key] = company
            self.stdout.write(
                self.style.SUCCESS(f"{'Créée' if created else 'Existe déjà'} : {company}")
            )

        for spec in DEMO_USERS:
            company = companies[spec["company"]] if spec["company"] else None
            prenom, _, nom_famille = spec["nom"].partition(" ")
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "role": spec["role"],
                    "company": company,
                    "first_name": prenom,
                    "last_name": nom_famille,
                    "email": f"{spec['username']}@demo.local",
                    "is_staff": spec["role"] == Role.SUPERADMIN,
                    "is_superuser": spec["role"] == Role.SUPERADMIN,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Créé' if created else 'Existe déjà'} : {user.username} "
                    f"(role={user.role}, company={company}) — mot de passe : {DEMO_PASSWORD}"
                )
            )
