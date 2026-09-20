import pytest

from core.models import Role
from formation.parcours_de_base import charger_parcours_de_base


@pytest.fixture
def parcours_de_base(db):
    charger_parcours_de_base()


@pytest.fixture
def guichetier_a(user_factory, company_a):
    return user_factory("guichetier_formation_a", Role.GUICHETIER, company=company_a)


@pytest.fixture
def guichetier_b(user_factory, company_b):
    return user_factory("guichetier_formation_b", Role.GUICHETIER, company=company_b)


@pytest.fixture
def chauffeur_a(user_factory, company_a):
    return user_factory("chauffeur_formation_a", Role.CHAUFFEUR_PRINCIPAL, company=company_a)


@pytest.fixture
def magasinier_a(user_factory, company_a):
    return user_factory("magasinier_formation_a", Role.MAGASINIER, company=company_a)


@pytest.fixture
def pdg_a(user_factory, company_a):
    return user_factory("pdg_formation_a", Role.PDG, company=company_a)
