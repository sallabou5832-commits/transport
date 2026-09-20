import pytest

from billetterie.models import ModePaiement, Ticket


@pytest.mark.django_db
class TestVenteTicket:
    def test_vente_ticket_success(self, api_client, guichetier_a, depart_a):
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
        assert response.data["vendu_par"] == guichetier_a.id
        assert Ticket.objects.filter(depart=depart_a, passager_nom="Awa Koné").exists()

        depart_a.refresh_from_db()
        assert depart_a.places_vendues == 1

    def test_refus_si_plus_de_place(self, api_client, guichetier_a, depart_a, vehicule_a):
        vehicule_a.capacite = 1
        vehicule_a.save()

        api_client.force_authenticate(user=guichetier_a)

        first = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Premier passager",
                "passager_telephone": "+2250700000001",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.ESPECES,
            },
        )
        assert first.status_code == 201

        second = api_client.post(
            "/api/tickets/",
            {
                "depart": depart_a.id,
                "passager_nom": "Deuxième passager",
                "passager_telephone": "+2250700000002",
                "prix": "5000.00",
                "mode_paiement": ModePaiement.MOBILE_MONEY,
            },
        )

        assert second.status_code == 400
        assert "depart" in second.data

        depart_a.refresh_from_db()
        assert depart_a.places_vendues == 1
        assert Ticket.objects.filter(depart=depart_a).count() == 1

    def test_vente_refusee_depart_termine(self, api_client, guichetier_a, depart_a):
        from billetterie.models import DepartStatut

        depart_a.statut = DepartStatut.TERMINE
        depart_a.save()

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

        assert response.status_code == 400
