import datetime

import pytest
from django.utils import timezone

from core.models import Role
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut
from billetterie.models import Depart, DepartStatut


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
        immatriculation="CI-1000-AA", capacite=3, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )


@pytest.fixture
def chauffeur_a(user_factory, company_a):
    return user_factory("chauffeur_a", Role.CHAUFFEUR_PRINCIPAL, company=company_a)


@pytest.fixture
def guichetier_a(user_factory, company_a):
    return user_factory("guichetier_a", Role.GUICHETIER, company=company_a)


@pytest.fixture
def guichetier_a2(user_factory, company_a):
    return user_factory("guichetier_a2", Role.GUICHETIER, company=company_a)


@pytest.fixture
def chef_gare_billetterie_a(user_factory, company_a):
    return user_factory("chef_gare_billet_a", Role.CHEF_GARE, company=company_a)


@pytest.fixture
def bagagiste_a(user_factory, company_a):
    return user_factory("bagagiste_a", Role.BAGAGISTE, company=company_a)


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
