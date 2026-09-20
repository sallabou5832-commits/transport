import pytest

from reseau.models import Vehicule, VehiculeStatut


@pytest.mark.django_db
class TestVehiculeCRUD:
    def test_create_vehicule(self, api_client, company_a_manager, company_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/vehicules/",
            {"immatriculation": "CI-9999-XY", "capacite": 60, "statut": VehiculeStatut.DISPONIBLE},
        )

        assert response.status_code == 201
        assert response.data["company"]["id"] == company_a.id

    def test_duplicate_immatriculation_rejected(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/vehicules/",
            {
                "immatriculation": vehicule_a.immatriculation,
                "capacite": 40,
                "statut": VehiculeStatut.DISPONIBLE,
            },
        )

        assert response.status_code == 400

    def test_list_only_shows_own_company(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.get("/api/vehicules/")

        ids = [v["id"] for v in response.data]
        assert vehicule_a.id in ids

    def test_update_statut(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.patch(
            f"/api/vehicules/{vehicule_a.id}/", {"statut": VehiculeStatut.EN_MAINTENANCE}
        )

        assert response.status_code == 200
        vehicule_a.refresh_from_db()
        assert vehicule_a.statut == VehiculeStatut.EN_MAINTENANCE

    def test_delete_vehicule(self, api_client, company_a_manager, vehicule_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.delete(f"/api/vehicules/{vehicule_a.id}/")

        assert response.status_code == 204
        assert not Vehicule.objects.filter(id=vehicule_a.id).exists()
