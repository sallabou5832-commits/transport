import datetime

import pytest
from django.utils import timezone

from core.models import Role
from reseau.models import Gare, Ligne
from rh.models import ObligationFormation

POSTES = (
    "drh", "qhse", "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "guichetier", "bagagiste",
    "chauffeur_principal", "chauffeur_relais", "controleur_ligne", "directeur_technique", "chef_atelier", "mecanicien",
    "responsable_juridique", "directeur_financier",
)


def jour(decalage=0):
    return timezone.localdate() + datetime.timedelta(days=decalage)


@pytest.fixture
def equipe(user_factory, company_a):
    """Un agent par poste, dans la compagnie A."""
    return {poste: user_factory(f"{poste}_rh", Role(poste), company=company_a) for poste in POSTES}


@pytest.fixture
def oser(company_a):
    """La formation de sécurité routière : obligatoire pour les conducteurs, valable 24 mois, préavis de 60 jours."""
    return ObligationFormation.objects.create(
        company=company_a, nom="Sécurité routière OSER", roles=["chauffeur_principal", "chauffeur_relais"], validite_mois=24, preavis_jours=60
    )


@pytest.fixture
def ligne_a(company_a):
    depart = Gare.objects.create(nom="Gare Départ RH", ville="Abidjan", company=company_a)
    arrivee = Gare.objects.create(nom="Gare Arrivée RH", ville="Bouaké", company=company_a)
    return Ligne.objects.create(nom="Abidjan-Bouaké RH", gare_depart=depart, gare_arrivee=arrivee, company=company_a)
