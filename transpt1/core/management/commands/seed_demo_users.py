import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

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

DEMO_USERS = [
    {"username": "pdg_stc", "role": Role.PDG, "company": "stc_voyages"},
    {"username": "secretaire_general_stc", "role": Role.SECRETAIRE_GENERAL, "company": "stc_voyages"},
    {"username": "qhse_stc", "role": Role.QHSE, "company": "stc_voyages"},
    {"username": "chef_gare_stc", "role": Role.CHEF_GARE, "company": "stc_voyages"},
    {"username": "guichetier_stc", "role": Role.GUICHETIER, "company": "stc_voyages"},
    {"username": "chauffeur_stc", "role": Role.CHAUFFEUR_PRINCIPAL, "company": "stc_voyages"},
    {"username": "chauffeur_relais_stc", "role": Role.CHAUFFEUR_RELAIS, "company": "stc_voyages"},
    {"username": "magasinier_stc", "role": Role.MAGASINIER, "company": "stc_voyages"},
    {"username": "chef_atelier_stc", "role": Role.CHEF_ATELIER, "company": "stc_voyages"},
    {"username": "pdg_savane", "role": Role.PDG, "company": "express_savane"},
    {"username": "chef_gare_savane", "role": Role.CHEF_GARE, "company": "express_savane"},
    {"username": "superadmin_demo", "role": Role.SUPERADMIN, "company": None},
]


class Command(BaseCommand):
    help = "Crée des compagnies et utilisateurs de démonstration pour les tests manuels."

    @transaction.atomic
    def handle(self, *args, **options):
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
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "role": spec["role"],
                    "company": company,
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
