import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from maintenance.models import OrdreReparation, Piece, StatutOrdreReparation
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut

ROLES = [
    "pdg", "qhse", "directeur_exploitation", "chef_gare", "chef_ligne", "guichetier", "chauffeur_principal",
    "directeur_technique", "magasinier", "chef_atelier", "mecanicien", "drh",
]


@pytest.fixture
def agents(user_factory, company_a):
    """Un agent par poste utile aux alertes, dans la compagnie A."""
    return {role: user_factory(f"{role}_alerte", getattr(Role, role.upper()), company=company_a) for role in ROLES}


@pytest.fixture
def reseau_a(company_a, agents):
    gare_depart = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=agents["chef_gare"])
    gare_arrivee = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a)
    ligne = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company_a)
    vehicule = Vehicule.objects.create(
        immatriculation="CI-4000-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=agents["chauffeur_principal"], company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=3), statut=DepartStatut.PLANIFIE,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=agents["chauffeur_principal"], company=company_a, heure_depart_prevue=depart.date_heure
    )
    return {"gare": gare_depart, "ligne": ligne, "vehicule": vehicule, "depart": depart, "feuille": feuille}


@pytest.fixture
def piece(company_a):
    return Piece.objects.create(nom="Filtre", reference="F-1", quantite_stock=6, seuil_alerte=5, company=company_a)


@pytest.fixture
def ordre(company_a, reseau_a, agents):
    return OrdreReparation.objects.create(
        vehicule=reseau_a["vehicule"], company=company_a, description="Révision",
        statut=StatutOrdreReparation.EN_COURS, mecanicien=agents["mecanicien"],
    )


def alertes_de(api_client, utilisateur):
    """Les alertes que voit `utilisateur`, telles que l'API les renvoie."""
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/alertes/").data["alertes"]
