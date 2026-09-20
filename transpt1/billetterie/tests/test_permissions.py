import pytest

from billetterie.models import ModePaiement, Ticket


@pytest.mark.django_db
class TestRestrictionRoleGuichetier:
    def test_guichetier_peut_vendre(self, api_client, guichetier_a, depart_a):
        api_client.force_authenticate(user=guichetier_a)

        response = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Awa Koné",
                "passager_telephone": "+2250700000000",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
            },
        )

        assert response.status_code == 201

    def test_role_superieur_peut_vendre(self, api_client, chef_gare_billetterie_a, depart_a):
        api_client.force_authenticate(user=chef_gare_billetterie_a)

        response = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Awa Koné",
                "passager_telephone": "+2250700000000",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
            },
        )

        assert response.status_code == 201

    def test_role_inferieur_ne_peut_pas_vendre(self, api_client, bagagiste_a, depart_a):
        api_client.force_authenticate(user=bagagiste_a)

        response = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Awa Koné",
                "passager_telephone": "+2250700000000",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
            },
        )

        assert response.status_code == 403
        assert not Ticket.objects.filter(depart=depart_a).exists()

    def test_utilisateur_non_authentifie_ne_peut_pas_vendre(self, api_client, depart_a):
        response = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Awa Koné",
                "passager_telephone": "+2250700000000",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
            },
        )

        assert response.status_code == 401
