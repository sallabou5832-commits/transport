import pytest


@pytest.mark.django_db
class TestChefGareRestriction:
    def test_chef_can_update_own_gare(self, api_client, chef_gare_a, gare_a):
        api_client.force_authenticate(user=chef_gare_a)

        response = api_client.patch(f"/api/gares/{gare_a.id}/", {"ville": "Cocody"})

        assert response.status_code == 200
        gare_a.refresh_from_db()
        assert gare_a.ville == "Cocody"

    def test_chef_can_delete_own_gare(self, api_client, chef_gare_a, gare_a):
        api_client.force_authenticate(user=chef_gare_a)

        response = api_client.delete(f"/api/gares/{gare_a.id}/")

        assert response.status_code == 204

    def test_chef_cannot_update_other_gare_same_company(
        self, api_client, chef_gare_a, gare_a2
    ):
        api_client.force_authenticate(user=chef_gare_a)

        response = api_client.patch(f"/api/gares/{gare_a2.id}/", {"ville": "Marcory"})

        assert response.status_code == 403

    def test_chef_cannot_delete_other_gare_same_company(
        self, api_client, chef_gare_a, gare_a2
    ):
        api_client.force_authenticate(user=chef_gare_a)

        response = api_client.delete(f"/api/gares/{gare_a2.id}/")

        assert response.status_code == 403

    def test_chef_can_still_read_other_gare_same_company(
        self, api_client, chef_gare_a, gare_a2
    ):
        api_client.force_authenticate(user=chef_gare_a)

        response = api_client.get(f"/api/gares/{gare_a2.id}/")

        assert response.status_code == 200

    def test_other_roles_unaffected_by_chef_restriction(
        self, api_client, company_a_manager, gare_a2
    ):
        api_client.force_authenticate(user=company_a_manager)

        response = api_client.patch(f"/api/gares/{gare_a2.id}/", {"ville": "Marcory"})

        assert response.status_code == 200
