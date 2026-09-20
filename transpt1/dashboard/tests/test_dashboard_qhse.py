import pytest

from core.models import Role


@pytest.mark.django_db
class TestDashboardQhse:
    def test_liste_les_incidents_ouverts_du_plus_grave_au_moins_grave(
        self, api_client, qhse_a, scenario_a, scenario_b_decoy
    ):
        api_client.force_authenticate(user=qhse_a)

        response = api_client.get("/api/dashboard/qhse/")

        assert response.status_code == 200
        incidents = scenario_a["incidents"]

        ids = [row["id"] for row in response.data]
        assert ids == [
            incidents["grave_recent"].id,
            incidents["grave_ancien"].id,
            incidents["moyenne_recent"].id,
            incidents["faible_recent"].id,
        ]
        assert incidents["grave_traite"].id not in ids

        premiere_ligne = response.data[0]
        assert premiere_ligne["gravite"] == "grave"
        assert premiere_ligne["vehicule"]["id"] == incidents["grave_recent"].vehicule_id

    def test_les_incidents_dune_autre_compagnie_ne_fuient_pas(
        self, api_client, qhse_a, scenario_a, scenario_b_decoy
    ):
        api_client.force_authenticate(user=qhse_a)

        response = api_client.get("/api/dashboard/qhse/")

        assert response.status_code == 200
        ids = {row["id"] for row in response.data}
        ids_b = {incident.id for incident in scenario_b_decoy["incidents"].values()}
        assert ids.isdisjoint(ids_b)

    def test_pdg_ne_peut_pas_consulter_le_dashboard_qhse(self, api_client, pdg_a, scenario_a):
        api_client.force_authenticate(user=pdg_a)

        response = api_client.get("/api/dashboard/qhse/")

        assert response.status_code == 403

    def test_role_sans_lien_ne_peut_pas_consulter(
        self, api_client, user_factory, company_a, scenario_a
    ):
        guichetier = user_factory("guichetier_qhse_test", Role.GUICHETIER, company=company_a)
        api_client.force_authenticate(user=guichetier)

        response = api_client.get("/api/dashboard/qhse/")

        assert response.status_code == 403
