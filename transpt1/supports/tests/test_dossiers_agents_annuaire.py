import datetime

import pytest

from core.models import Role
from supports.models import DossierAgent


@pytest.mark.django_db
class TestIdentiteDansLeDossier:
    def test_le_drh_voit_le_nom_et_le_role_de_chaque_agent(self, api_client, drh_a, agent_a, dossier_agent_a):
        agent_a.first_name, agent_a.last_name = "Koffi", "Yao"
        agent_a.save()
        api_client.force_authenticate(user=drh_a)

        dossier = api_client.get("/api/dossiers-agents/").data[0]

        assert dossier["agent_nom"] == "Koffi Yao"
        assert dossier["agent_role"] == "guichetier"

    def test_sans_nom_renseigne_on_affiche_l_identifiant(self, api_client, drh_a, agent_a, dossier_agent_a):
        api_client.force_authenticate(user=drh_a)

        assert api_client.get("/api/dossiers-agents/").data[0]["agent_nom"] == agent_a.username

    def test_un_agent_ne_voit_que_son_propre_dossier(
        self, api_client, company_a, agent_a, agent_a2, dossier_agent_a
    ):
        DossierAgent.objects.create(
            agent=agent_a2, company=company_a, date_embauche=datetime.date(2023, 5, 1), poste="Guichetier"
        )
        api_client.force_authenticate(user=agent_a)

        dossiers = api_client.get("/api/dossiers-agents/").data

        assert [d["agent"] for d in dossiers] == [agent_a.id]


@pytest.mark.django_db
class TestAgentsSansDossier:
    def test_liste_les_agents_de_la_compagnie_sans_dossier(
        self, api_client, drh_a, agent_a, agent_a2, dossier_agent_a
    ):
        api_client.force_authenticate(user=drh_a)

        reponse = api_client.get("/api/dossiers-agents/agents-sans-dossier/")

        assert reponse.status_code == 200
        usernames = [a["username"] for a in reponse.data]
        assert agent_a2.username in usernames  # n'a pas de dossier
        assert agent_a.username not in usernames  # en a un
        assert drh_a.username in usernames  # le DRH lui-même n'a pas de dossier
        assert {"id", "username", "nom", "role"} == set(reponse.data[0])

    def test_n_expose_aucun_agent_d_une_autre_compagnie(
        self, api_client, drh_a, user_factory, company_b, agent_a2
    ):
        etranger = user_factory("agent_b_secret", Role.GUICHETIER, company=company_b)
        api_client.force_authenticate(user=drh_a)

        usernames = [a["username"] for a in api_client.get("/api/dossiers-agents/agents-sans-dossier/").data]

        assert etranger.username not in usernames

    def test_le_superadmin_n_est_jamais_propose(self, api_client, drh_a, superadmin_user):
        api_client.force_authenticate(user=drh_a)

        usernames = [a["username"] for a in api_client.get("/api/dossiers-agents/agents-sans-dossier/").data]

        assert superadmin_user.username not in usernames

    @pytest.mark.parametrize("role", [r.value for r in Role if r not in (Role.DRH, Role.SUPERADMIN)])
    def test_reserve_au_drh(self, api_client, user_factory, company_a, role):
        api_client.force_authenticate(user=user_factory(f"{role}_annuaire", Role(role), company=company_a))

        assert api_client.get("/api/dossiers-agents/agents-sans-dossier/").status_code == 403

    def test_le_superadmin_n_y_accede_pas_non_plus(self, api_client, superadmin_user):
        api_client.force_authenticate(user=superadmin_user)

        assert api_client.get("/api/dossiers-agents/agents-sans-dossier/").status_code == 403

    def test_un_dossier_ouvert_retire_l_agent_de_la_liste(self, api_client, drh_a, agent_a2):
        api_client.force_authenticate(user=drh_a)
        creation = api_client.post(
            "/api/dossiers-agents/",
            {"agent": agent_a2.id, "date_embauche": "2024-02-01", "poste": "Guichetier"},
        )
        assert creation.status_code == 201

        usernames = [a["username"] for a in api_client.get("/api/dossiers-agents/agents-sans-dossier/").data]

        assert agent_a2.username not in usernames
