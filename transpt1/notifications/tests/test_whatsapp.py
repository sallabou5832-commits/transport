import json
from unittest.mock import MagicMock, patch

import pytest

from billetterie.models import ModePaiement
from notifications.models import CanalNotification, NotificationLog, StatutNotification
from notifications.services import envoyer_whatsapp

NUMERO_CI = "+2250700000000"
DONNEES_VENTE = {
    "passager_nom": "Awa Koné",
    "passager_telephone": NUMERO_CI,
    "prix": "5000.00",
    "mode_paiement": ModePaiement.ESPECES,
}


@pytest.fixture(autouse=True)
def config_whatsapp(settings):
    settings.NOTIFICATIONS_SIMULATION_MODE = True
    settings.NOTIFICATIONS_CANAUX_TICKET = ["sms", "whatsapp"]
    settings.NOTIFICATIONS_SMS_PROVIDER = "twilio"
    settings.TWILIO_ACCOUNT_SID = "ACtest"
    settings.TWILIO_AUTH_TOKEN = "token-test"
    settings.TWILIO_FROM_NUMBER = "+15005550006"
    settings.TWILIO_WHATSAPP_FROM = "+14155238886"
    settings.TWILIO_WHATSAPP_CONTENT_SID = ""


def vendre(api_client, guichetier, depart):
    api_client.force_authenticate(user=guichetier)
    response = api_client.post("/api/tickets/", {"depart": depart.id, **DONNEES_VENTE})
    assert response.status_code == 201
    return response.data["id"]


@pytest.mark.django_db
class TestCanauxDeLaVente:
    def test_vente_cree_une_trace_sms_et_une_trace_whatsapp_simulees(
        self, api_client, guichetier_a, depart_a, company_a
    ):
        ticket_id = vendre(api_client, guichetier_a, depart_a)

        logs = {log.canal: log for log in NotificationLog.objects.filter(ticket_id=ticket_id)}
        assert set(logs) == {CanalNotification.SMS, CanalNotification.WHATSAPP}
        whatsapp = logs[CanalNotification.WHATSAPP]
        assert whatsapp.statut == StatutNotification.SIMULE
        assert whatsapp.fournisseur == "twilio"
        assert whatsapp.destinataire == NUMERO_CI
        assert whatsapp.company_id == company_a.id
        assert "Awa Koné" in whatsapp.contenu and depart_a.ligne.nom in whatsapp.contenu
        assert logs[CanalNotification.SMS].contenu == whatsapp.contenu

    def test_whatsapp_seul(self, api_client, guichetier_a, depart_a, settings):
        settings.NOTIFICATIONS_CANAUX_TICKET = ["whatsapp"]

        vendre(api_client, guichetier_a, depart_a)

        assert list(NotificationLog.objects.values_list("canal", flat=True)) == [
            CanalNotification.WHATSAPP
        ]

    def test_sms_seul(self, api_client, guichetier_a, depart_a, settings):
        settings.NOTIFICATIONS_CANAUX_TICKET = ["sms"]

        vendre(api_client, guichetier_a, depart_a)

        assert list(NotificationLog.objects.values_list("canal", flat=True)) == [
            CanalNotification.SMS
        ]

    def test_canal_inconnu_est_ignore_sans_bloquer_les_autres(
        self, api_client, guichetier_a, depart_a, settings
    ):
        settings.NOTIFICATIONS_CANAUX_TICKET = ["telegram", "whatsapp"]

        vendre(api_client, guichetier_a, depart_a)

        assert list(NotificationLog.objects.values_list("canal", flat=True)) == [
            CanalNotification.WHATSAPP
        ]

    def test_aucun_canal_configure_la_vente_reussit_sans_notification(
        self, api_client, guichetier_a, depart_a, settings
    ):
        settings.NOTIFICATIONS_CANAUX_TICKET = []

        vendre(api_client, guichetier_a, depart_a)

        assert not NotificationLog.objects.exists()

    def test_simulation_n_appelle_pas_twilio(self, api_client, guichetier_a, depart_a):
        with patch("twilio.rest.Client") as client:
            vendre(api_client, guichetier_a, depart_a)

        client.assert_not_called()

    def test_l_echec_de_whatsapp_n_empeche_ni_la_vente_ni_le_sms(
        self, api_client, guichetier_a, depart_a, settings
    ):
        settings.NOTIFICATIONS_SIMULATION_MODE = False
        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.side_effect = [
                MagicMock(sid="SM-sms"),
                RuntimeError("numéro non inscrit sur WhatsApp"),
            ]
            ticket_id = vendre(api_client, guichetier_a, depart_a)

        logs = {log.canal: log for log in NotificationLog.objects.filter(ticket_id=ticket_id)}
        assert logs[CanalNotification.SMS].statut == StatutNotification.ENVOYE
        assert logs[CanalNotification.WHATSAPP].statut == StatutNotification.ECHEC
        assert "non inscrit" in logs[CanalNotification.WHATSAPP].erreur


@pytest.mark.django_db
class TestEnvoiWhatsappTwilio:
    def test_message_libre(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = False

        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.return_value.sid = "SM123"
            log = envoyer_whatsapp(NUMERO_CI, "Bonjour Awa", company=company_a)

        client.assert_called_once_with("ACtest", "token-test")
        client.return_value.messages.create.assert_called_once_with(
            from_="whatsapp:+14155238886", to=f"whatsapp:{NUMERO_CI}", body="Bonjour Awa"
        )
        assert log.canal == CanalNotification.WHATSAPP
        assert log.statut == StatutNotification.ENVOYE
        assert log.fournisseur == "twilio"
        assert log.reference_fournisseur == "SM123"

    def test_modele_approuve_utilise_quand_configure(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = False
        settings.TWILIO_WHATSAPP_CONTENT_SID = "HXmodele"
        variables = {"1": "Awa Koné", "2": "Adjamé-Bouaké", "3": "01/01/2027 à 08:00", "4": "5000.00"}

        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.return_value.sid = "SM456"
            log = envoyer_whatsapp(NUMERO_CI, "texte libre", company=company_a, variables=variables)

        appel = client.return_value.messages.create.call_args.kwargs
        assert appel["content_sid"] == "HXmodele"
        assert json.loads(appel["content_variables"]) == variables
        assert "body" not in appel
        assert appel["to"] == f"whatsapp:{NUMERO_CI}"
        assert log.statut == StatutNotification.ENVOYE

    def test_modele_configure_sans_variables_retombe_sur_le_message_libre(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = False
        settings.TWILIO_WHATSAPP_CONTENT_SID = "HXmodele"

        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.return_value.sid = "SM789"
            envoyer_whatsapp(NUMERO_CI, "texte libre", company=company_a)

        appel = client.return_value.messages.create.call_args.kwargs
        assert appel["body"] == "texte libre"
        assert "content_sid" not in appel

    def test_expediteur_absent_donne_un_echec_trace(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = False
        settings.TWILIO_WHATSAPP_FROM = ""

        with patch("twilio.rest.Client") as client:
            log = envoyer_whatsapp(NUMERO_CI, "Bonjour", company=company_a)

        client.assert_not_called()
        assert log.statut == StatutNotification.ECHEC
        assert "TWILIO_WHATSAPP_FROM" in log.erreur

    def test_erreur_twilio_est_tracee_sans_lever(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = False

        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.side_effect = RuntimeError("modèle non approuvé")
            log = envoyer_whatsapp(NUMERO_CI, "Bonjour", company=company_a)

        assert log.statut == StatutNotification.ECHEC
        assert log.erreur == "modèle non approuvé"
