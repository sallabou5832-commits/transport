import pytest

from reseau.models import Gare


@pytest.mark.django_db
class TestGareCRUD:
    def test_create_gare(self, api_client, company_a_manager, company_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/gares/", {"nom": "Gare Treichville", "ville": "Abidjan"}
        )

        assert response.status_code == 201
        assert response.data["company"]["id"] == company_a.id
        assert Gare.objects.filter(nom="Gare Treichville", company=company_a).exists()

    def test_list_only_shows_own_company(
        self, api_client, company_a_manager, gare_a, gare_b
    ):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.get("/api/gares/")

        ids = [g["id"] for g in response.data]
        assert gare_a.id in ids
        assert gare_b.id not in ids

    def test_retrieve_other_company_gare_not_found(self, api_client, company_a_manager, gare_b):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.get(f"/api/gares/{gare_b.id}/")

        assert response.status_code == 404

    def test_update_own_company_gare(self, api_client, company_a_manager, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.patch(f"/api/gares/{gare_a.id}/", {"ville": "Cocody"})

        assert response.status_code == 200
        gare_a.refresh_from_db()
        assert gare_a.ville == "Cocody"

    def test_delete_own_company_gare(self, api_client, company_a_manager, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.delete(f"/api/gares/{gare_a.id}/")

        assert response.status_code == 204
        assert not Gare.objects.filter(id=gare_a.id).exists()

    def test_anonymous_denied(self, api_client, gare_a):
        response = api_client.get("/api/gares/")
        assert response.status_code == 401
