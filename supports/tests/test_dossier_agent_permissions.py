import pytest

from supports.models import DossierAgent


@pytest.mark.django_db
class TestPermissionsDossierAgent:
    def test_drh_peut_creer_un_dossier(self, api_client, drh_a, agent_a):
        api_client.force_authenticate(user=drh_a)

        response = api_client.post(
            "/api/dossiers-agents/",
            {
                "agent": agent_a.id,
                "date_embauche": "2023-05-01",
                "poste": "Guichetier principal",
                "notes_rh": "Bon élément.",
            },
        )

        assert response.status_code == 201

    def test_drh_peut_lister_tous_les_dossiers(self, api_client, drh_a, dossier_agent_a):
        api_client.force_authenticate(user=drh_a)

        response = api_client.get("/api/dossiers-agents/")

        assert response.status_code == 200
        ids = [d["id"] for d in response.data]
        assert dossier_agent_a.id in ids

    def test_agent_peut_voir_son_propre_dossier(self, api_client, agent_a, dossier_agent_a):
        api_client.force_authenticate(user=agent_a)

        response = api_client.get(f"/api/dossiers-agents/{dossier_agent_a.id}/")

        assert response.status_code == 200

    def test_agent_ne_voit_pas_le_dossier_dun_autre_dans_la_liste(
        self, api_client, agent_a2, dossier_agent_a
    ):
        api_client.force_authenticate(user=agent_a2)

        response = api_client.get("/api/dossiers-agents/")

        assert response.status_code == 200
        ids = [d["id"] for d in response.data]
        assert dossier_agent_a.id not in ids

    def test_agent_ne_peut_pas_consulter_le_dossier_dun_autre(
        self, api_client, agent_a2, dossier_agent_a
    ):
        api_client.force_authenticate(user=agent_a2)

        response = api_client.get(f"/api/dossiers-agents/{dossier_agent_a.id}/")

        assert response.status_code == 404

    def test_agent_ne_peut_pas_modifier_son_propre_dossier(
        self, api_client, agent_a, dossier_agent_a
    ):
        api_client.force_authenticate(user=agent_a)

        response = api_client.patch(
            f"/api/dossiers-agents/{dossier_agent_a.id}/", {"notes_rh": "Modification interdite"}
        )

        assert response.status_code == 403
        dossier_agent_a.refresh_from_db()
        assert dossier_agent_a.notes_rh == "RAS"

    def test_role_non_drh_ne_peut_pas_creer_un_dossier(
        self, api_client, responsable_juridique_a, agent_a2
    ):
        api_client.force_authenticate(user=responsable_juridique_a)

        response = api_client.post(
            "/api/dossiers-agents/",
            {
                "agent": agent_a2.id,
                "date_embauche": "2023-05-01",
                "poste": "Guichetier",
            },
        )

        assert response.status_code == 403
        assert not DossierAgent.objects.filter(agent=agent_a2).exists()
