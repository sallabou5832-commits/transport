import pytest

from core.models import Role
from reseau.models import Gare, Ligne, Vehicule, VehiculeStatut


@pytest.fixture
def company_a_manager(user_factory, company_a):
    return user_factory("directeur_a", Role.DIRECTEUR_EXPLOITATION, company=company_a)


@pytest.fixture
def company_b_manager(user_factory, company_b):
    return user_factory("directeur_b", Role.DIRECTEUR_EXPLOITATION, company=company_b)


@pytest.fixture
def gare_a(db, company_a):
    return Gare.objects.create(nom="Gare Adjamé", ville="Abidjan", company=company_a)


@pytest.fixture
def gare_a2(db, company_a):
    return Gare.objects.create(nom="Gare Yopougon", ville="Abidjan", company=company_a)


@pytest.fixture
def gare_b(db, company_b):
    return Gare.objects.create(nom="Gare Bouaké Centre", ville="Bouaké", company=company_b)


@pytest.fixture
def chef_gare_a(user_factory, company_a, gare_a):
    user = user_factory("chef_de_gare_a", Role.CHEF_GARE, company=company_a)
    gare_a.chef = user
    gare_a.save()
    return user


@pytest.fixture
def ligne_a(db, company_a, gare_a, gare_a2):
    return Ligne.objects.create(
        nom="Adjamé-Yopougon", gare_depart=gare_a, gare_arrivee=gare_a2, company=company_a
    )


@pytest.fixture
def vehicule_a(db, company_a):
    return Vehicule.objects.create(
        immatriculation="CI-1234-AB", capacite=70, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )
