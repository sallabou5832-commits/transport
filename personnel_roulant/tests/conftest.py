import datetime

import pytest
from django.utils import timezone

from billetterie.models import Depart, DepartStatut
from core.models import Role
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


@pytest.fixture
def gare_depart_a(db, company_a):
    return Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)


@pytest.fixture
def gare_arrivee_a(db, company_a):
    return Gare.objects.create(nom="Gare Bouaké", ville="Bouaké", company=company_a)


@pytest.fixture
def ligne_a(db, company_a, gare_depart_a, gare_arrivee_a):
    return Ligne.objects.create(
        nom="Adjamé-Bouaké", gare_depart=gare_depart_a, gare_arrivee=gare_arrivee_a, company=company_a
    )


@pytest.fixture
def vehicule_a(db, company_a):
    return Vehicule.objects.create(
        immatriculation="CI-2000-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )


@pytest.fixture
def chauffeur_a(user_factory, company_a):
    return user_factory("chauffeur_pr_a", Role.CHAUFFEUR_PRINCIPAL, company=company_a)


@pytest.fixture
def chauffeur_a2(user_factory, company_a):
    return user_factory("chauffeur_pr_a2", Role.CHAUFFEUR_PRINCIPAL, company=company_a)


@pytest.fixture
def qhse_a(user_factory, company_a):
    return user_factory("qhse_a", Role.QHSE, company=company_a)


@pytest.fixture
def directeur_exploitation_a(user_factory, company_a):
    return user_factory("directeur_exploit_a", Role.DIRECTEUR_EXPLOITATION, company=company_a)


@pytest.fixture
def chef_ligne_a(user_factory, company_a):
    return user_factory("chef_ligne_a", Role.CHEF_LIGNE, company=company_a)


@pytest.fixture
def depart_a(db, company_a, ligne_a, vehicule_a, chauffeur_a):
    return Depart.objects.create(
        ligne=ligne_a,
        vehicule=vehicule_a,
        chauffeur=chauffeur_a,
        company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=2),
        statut=DepartStatut.PLANIFIE,
    )


@pytest.fixture
def depart_a2(db, company_a, ligne_a, vehicule_a, chauffeur_a2):
    return Depart.objects.create(
        ligne=ligne_a,
        vehicule=vehicule_a,
        chauffeur=chauffeur_a2,
        company=company_a,
        date_heure=timezone.now() + datetime.timedelta(hours=4),
        statut=DepartStatut.PLANIFIE,
    )


@pytest.fixture
def feuille_a(db, company_a, depart_a, chauffeur_a):
    return FeuilleDeRoute.objects.create(
        depart=depart_a,
        chauffeur=chauffeur_a,
        company=company_a,
        heure_depart_prevue=depart_a.date_heure,
    )


@pytest.fixture
def feuille_a2(db, company_a, depart_a2, chauffeur_a2):
    return FeuilleDeRoute.objects.create(
        depart=depart_a2,
        chauffeur=chauffeur_a2,
        company=company_a,
        heure_depart_prevue=depart_a2.date_heure,
    )
