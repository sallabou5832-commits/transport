"""Fixtures partagées par les tests du suivi de trajet (positions, fatigue, relais)."""

import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut

ROLES = [
    "chef_ligne", "chef_gare", "directeur_exploitation", "pdg", "qhse", "directeur_technique", "guichetier", "drh",
    "controleur_ligne", "secretaire_general",
]


@pytest.fixture
def equipe(user_factory, company_a):
    agents = {role: user_factory(f"{role}_suivi", getattr(Role, role.upper()), company=company_a) for role in ROLES}
    agents["conducteur"] = user_factory("conducteur_suivi", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
    agents["relais"] = user_factory("relais_suivi", Role.CHAUFFEUR_RELAIS, company=company_a)
    agents["autre"] = user_factory("autre_chauffeur_suivi", Role.CHAUFFEUR_PRINCIPAL, company=company_a)
    return agents


@pytest.fixture
def trajet(company_a, equipe):
    """Un trajet en cours : Adjamé → Bouaké, parti il y a une heure, conduit par `conducteur`."""
    gare_depart = Gare.objects.create(
        nom="Adjamé", ville="Abidjan", company=company_a, chef=equipe["chef_gare"], latitude="5.360000", longitude="-4.008300"
    )
    gare_arrivee = Gare.objects.create(nom="Bouaké", ville="Bouaké", company=company_a, latitude="7.690600", longitude="-5.030000")
    ligne = Ligne.objects.create(nom="Adjamé-Bouaké", gare_depart=gare_depart, gare_arrivee=gare_arrivee, company=company_a)
    vehicule = Vehicule.objects.create(
        immatriculation="CI-9100-AA", capacite=40, statut=VehiculeStatut.EN_LIGNE, company=company_a
    )
    depart_reel = timezone.now() - datetime.timedelta(hours=1)
    depart = Depart.objects.create(
        ligne=ligne, vehicule=vehicule, chauffeur=equipe["conducteur"], company=company_a,
        date_heure=depart_reel, statut=DepartStatut.EN_COURS,
    )
    feuille = FeuilleDeRoute.objects.create(
        depart=depart, chauffeur=equipe["conducteur"], company=company_a, heure_depart_prevue=depart_reel,
        heure_depart_reelle=depart_reel,
    )
    return {"gare_depart": gare_depart, "gare_arrivee": gare_arrivee, "ligne": ligne, "vehicule": vehicule, "depart": depart, "feuille": feuille}


def partir_il_y_a(trajet, duree):
    """Recule le départ réel du trajet (pour simuler une longue conduite)."""
    moment = timezone.now() - duree
    trajet["feuille"].heure_depart_reelle = moment
    trajet["feuille"].heure_depart_prevue = moment
    trajet["feuille"].save()
    return moment
