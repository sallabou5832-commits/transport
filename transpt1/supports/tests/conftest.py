import datetime

import pytest
from django.utils import timezone

from core.models import Role
from reseau.models import Vehicule, VehiculeStatut
from supports.models import Assurance, DossierAgent


@pytest.fixture
def vehicule_a(db, company_a):
    return Vehicule.objects.create(
        immatriculation="CI-4000-AA", capacite=30, statut=VehiculeStatut.DISPONIBLE, company=company_a
    )


@pytest.fixture
def drh_a(user_factory, company_a):
    return user_factory("drh_a", Role.DRH, company=company_a)


@pytest.fixture
def agent_a(user_factory, company_a):
    return user_factory("agent_a", Role.GUICHETIER, company=company_a)


@pytest.fixture
def agent_a2(user_factory, company_a):
    return user_factory("agent_a2", Role.GUICHETIER, company=company_a)


@pytest.fixture
def responsable_juridique_a(user_factory, company_a):
    return user_factory("responsable_juridique_a", Role.RESPONSABLE_JURIDIQUE, company=company_a)


@pytest.fixture
def directeur_technique_a(user_factory, company_a):
    return user_factory("directeur_technique_a", Role.DIRECTEUR_TECHNIQUE, company=company_a)


@pytest.fixture
def directeur_financier_a(user_factory, company_a):
    return user_factory("directeur_financier_a", Role.DIRECTEUR_FINANCIER, company=company_a)


@pytest.fixture
def dossier_agent_a(db, company_a, agent_a):
    return DossierAgent.objects.create(
        agent=agent_a,
        company=company_a,
        date_embauche=datetime.date(2022, 1, 10),
        poste="Guichetier",
        notes_rh="RAS",
    )


@pytest.fixture
def assurance_proche_a(db, company_a, vehicule_a):
    return Assurance.objects.create(
        vehicule=vehicule_a,
        company=company_a,
        compagnie_assurance="NSIA Assurances",
        numero_police="POL-2024-001",
        date_echeance=timezone.localdate() + datetime.timedelta(days=10),
    )


@pytest.fixture
def assurance_lointaine_a(db, company_a, vehicule_a):
    return Assurance.objects.create(
        vehicule=vehicule_a,
        company=company_a,
        compagnie_assurance="NSIA Assurances",
        numero_police="POL-2024-002",
        date_echeance=timezone.localdate() + datetime.timedelta(days=90),
    )
