import pytest

from billetterie.models import ModePaiement


@pytest.mark.django_db
class TestPlacesRestantes:
    def test_jauge_initiale(self, api_client, guichetier_a, depart_a, vehicule_a):
        api_client.force_authenticate(user=guichetier_a)

        response = api_client.get(f"/api/departs/{depart_a.id}/places-restantes/")

        assert response.status_code == 200
        assert response.data["capacite"] == vehicule_a.capacite
        assert response.data["places_vendues"] == 0
        assert response.data["places_restantes"] == vehicule_a.capacite

    def test_jauge_apres_vente(self, api_client, guichetier_a, depart_a, vehicule_a):
        api_client.force_authenticate(user=guichetier_a)

        api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Awa Koné",
                "passager_telephone": "+2250700000000",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
            },
        )

        response = api_client.get(f"/api/departs/{depart_a.id}/places-restantes/")

        assert response.status_code == 200
        assert response.data["places_vendues"] == 1
        assert response.data["places_restantes"] == vehicule_a.capacite - 1
