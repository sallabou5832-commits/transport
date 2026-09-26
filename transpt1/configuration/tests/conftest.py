import pytest

from core.models import Role

ROLES = [
    "pdg", "secretaire_general", "directeur_exploitation", "chef_gare", "chef_ligne", "guichetier", "bagagiste",
    "chauffeur_principal", "controleur_ligne", "directeur_technique", "magasinier", "chef_atelier", "mecanicien",
    "drh", "qhse",
]


@pytest.fixture
def agents(user_factory, company_a):
    return {role: user_factory(f"{role}_config", getattr(Role, role.upper()), company=company_a) for role in ROLES}


def regler_poste(api_client, utilisateur, role, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.put(f"/api/configuration/postes/{role}/", corps, format="json")


def regler_agent(api_client, utilisateur, agent, **corps):
    api_client.force_authenticate(user=utilisateur)
    return api_client.put(f"/api/configuration/agents/{agent.id}/", corps, format="json")


def ma_configuration(api_client, utilisateur):
    api_client.force_authenticate(user=utilisateur)
    return api_client.get("/api/configuration/moi/").data
