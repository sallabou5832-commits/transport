import pytest

from billetterie.models import ModePaiement
from notifications.models import CanalNotification, NotificationLog, StatutNotification
from notifications.services import envoyer_sms


@pytest.mark.django_db
class TestNotificationVenteTicket:
    def test_vente_ticket_cree_un_notificationlog_simule(
        self, api_client, guichetier_a, depart_a, company_a, settings
    ):
        settings.NOTIFICATIONS_SIMULATION_MODE = True
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

        log = NotificationLog.objects.get(
            ticket_id=response.data["id"], canal=CanalNotification.SMS
        )
        assert log.statut == StatutNotification.SIMULE
        assert log.canal == CanalNotification.SMS
        assert log.destinataire == "+2250700000000"
        assert log.company_id == company_a.id
        assert log.reference_fournisseur == ""
        assert log.erreur == ""

    def test_contenu_notification_contient_les_infos_du_depart(
        self, api_client, guichetier_a, depart_a, settings
    ):
        settings.NOTIFICATIONS_SIMULATION_MODE = True
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

        log = NotificationLog.objects.get(
            ticket_id=response.data["id"], canal=CanalNotification.SMS
        )
        assert "Awa Koné" in log.contenu
        assert depart_a.ligne.nom in log.contenu
        assert "5000.00" in log.contenu

    def test_pas_de_notification_si_la_vente_echoue(self, api_client, guichetier_a, depart_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = True
        depart_a.vehicule.capacite = 0
        depart_a.vehicule.save()

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
        assert not NotificationLog.objects.exists()


@pytest.mark.django_db
class TestServiceEnvoyerSms:
    def test_simulation_ne_contacte_pas_de_fournisseur_reel(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = True

        log = envoyer_sms("+2250700000000", "Message de test", company=company_a)

        assert log.pk is not None
        assert log.statut == StatutNotification.SIMULE
        assert log.ticket is None
        assert NotificationLog.objects.count() == 1
