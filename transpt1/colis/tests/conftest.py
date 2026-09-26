import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut, ModePaiement, Ticket
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import AffectationGare, Gare, Ligne, Vehicule, VehiculeStatut

ROLES = [
    "bagagiste", "chef_gare", "chef_ligne", "directeur_exploitation", "pdg", "guichetier", "controleur_ligne",
    "chauffeur_principal", "qhse", "drh", "directeur_financier", "magasinier",
]


@pytest.fixture
def agents(user_factory, company_a):
    utilisateurs = {role: user_factory(f"{role}_colis", getattr(Role, role.upper()), company=company_a) for role in ROLES}
    utilisateurs["bagagiste_arrivee"] = user_factory("bagagiste_arrivee_colis", Role.BAGAGISTE, company=company_a)
    utilisateurs["chef_gare_arrivee"] = user_factory("chef_gare_arrivee_colis", Role.CHEF_GARE, company=company_a)
    return utilisateurs


@pytest.fixture
def monde(company_a, agents):
    gare_depart = Gare.objects.create(nom="Adjamé", ville="Abidjan", company=company_a, chef=agents["chef_gare"])
    gare_arrivee = Gare.objects.create(
        nom="Bouaké", ville="Bouaké", company=company_a, chef=agents["chef_gare_arrivee"]
    )
    AffectationGare.objects.create(agent=agents["bagagiste"], gare=gare_depart, company=company_a)
    AffectationGare.objects.create(agent=agents["bagagiste_arrivee"], gare=gare_arrivee, company=company_a)
    ligne = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company_a)
    vehicule = Vehicule.objects.create(
        immatriculation="CI-5000-AA", capacite=40, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=agents["chauffeur_principal"], company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=3), statut=DepartStatut.PLANIFIE,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=agents["chauffeur_principal"], company=company_a, heure_depart_prevue=depart.date_heure
    )
    ticket = Ticket.objects.create(
        depart=depart, company=company_a, passager_nom="Awa Kone", passager_telephone="0700000001",
        prix=Decimal("5000"), mode_paiement=ModePaiement.ESPECES, vendu_par=agents["guichetier"],
    )
    return {
        "gare_depart": gare_depart, "gare_arrivee": gare_arrivee, "ligne": ligne, "vehicule": vehicule,
        "depart": depart, "feuille": feuille, "ticket": ticket,
    }


def corps_colis(monde, **champs):
    """Corps d'une requête d'enregistrement ; un champ à None est omis de la requête."""
    corps = {
        "depart": monde["depart"].id, "type_colis": "colis", "description": "Carton de pagnes", "poids_kg": "12.5",
        "valeur_declaree": "50000", "frais": "2000", "mode_paiement": "especes",
        "expediteur_nom": "Issa Kone", "expediteur_telephone": "0700000002",
        "destinataire_nom": "Mariam Toure", "destinataire_telephone": "0700000003", **champs,
    }
    return {cle: valeur for cle, valeur in corps.items() if valeur is not None}


def enregistrer(api_client, utilisateur, monde, **champs):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post("/api/colis/", corps_colis(monde, **champs))


def agir(api_client, utilisateur, colis_id, action, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.post(f"/api/colis/{colis_id}/{action}/", corps)
