import pytest

from reseau.models import Ligne


@pytest.mark.django_db
class TestLigneCRUD:
    def test_create_ligne(self, api_client, company_a_manager, company_a, gare_a, gare_a2):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/lignes/",
            {"nom": "Adjame-Yopougon", "gare_depart": gare_a.id, "gare_arrivee": gare_a2.id},
        )

        assert response.status_code == 201
        assert response.data["company"]["id"] == company_a.id

    def test_cannot_use_gare_from_another_company(
        self, api_client, company_a_manager, gare_a, gare_b
    ):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/lignes/",
            {"nom": "Invalide", "gare_depart": gare_a.id, "gare_arrivee": gare_b.id},
        )

        assert response.status_code == 400

    def test_depart_and_arrivee_must_differ(self, api_client, company_a_manager, gare_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.post(
            "/api/lignes/",
            {"nom": "Boucle", "gare_depart": gare_a.id, "gare_arrivee": gare_a.id},
        )

        assert response.status_code == 400

    def test_list_only_shows_own_company(self, api_client, company_a_manager, ligne_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.get("/api/lignes/")

        ids = [ligne["id"] for ligne in response.data]
        assert ligne_a.id in ids

    def test_update_ligne(self, api_client, company_a_manager, ligne_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.patch(f"/api/lignes/{ligne_a.id}/", {"nom": "Nouveau nom"})

        assert response.status_code == 200
        ligne_a.refresh_from_db()
        assert ligne_a.nom == "Nouveau nom"

    def test_delete_ligne(self, api_client, company_a_manager, ligne_a):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.delete(f"/api/lignes/{ligne_a.id}/")

        assert response.status_code == 204
        assert not Ligne.objects.filter(id=ligne_a.id).exists()
