from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest
from django.core.cache import cache

from notifications.models import NotificationLog, StatutNotification
from notifications.providers import (
    ORANGE_TOKEN_CACHE_KEY,
    choisir_fournisseur,
    normaliser_numero,
)
from notifications.services import envoyer_sms

NUMERO_CI = "+2250700000000"
NUMERO_ETRANGER = "+33612345678"


@pytest.fixture(autouse=True)
def config_fournisseurs(settings):
    settings.NOTIFICATIONS_SIMULATION_MODE = False
    settings.NOTIFICATIONS_SMS_PROVIDER = "auto"
    settings.TWILIO_ACCOUNT_SID = "ACtest"
    settings.TWILIO_AUTH_TOKEN = "token-test"
    settings.TWILIO_FROM_NUMBER = "+15005550006"
    settings.ORANGE_SMS_CLIENT_ID = "orange-id"
    settings.ORANGE_SMS_CLIENT_SECRET = "orange-secret"
    settings.ORANGE_SMS_SENDER = "+2250000"
    settings.ORANGE_SMS_SENDER_NAME = ""
    cache.clear()


def reponse_http(status=200, json=None, text=""):
    reponse = MagicMock()
    reponse.status_code = status
    reponse.ok = status < 400
    reponse.json.return_value = json or {}
    reponse.text = text
    if not reponse.ok:
        reponse.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
    return reponse


REPONSE_JETON = reponse_http(json={"access_token": "jeton-orange", "expires_in": 7776000})
REPONSE_ENVOI = reponse_http(
    201,
    json={
        "outboundSMSMessageRequest": {
            "resourceURL": "https://api.orange.com/smsmessaging/v1/outbound/tel%3A%2B2250000/requests/msg-42"
        }
    },
)


class TestNormaliserNumero:
    @pytest.mark.parametrize(
        "saisi, attendu",
        [
            ("+2250700000000", "+2250700000000"),
            ("+225 07 00 00 00 00", "+2250700000000"),
            ("002250700000000", "+2250700000000"),
            ("07 00 00 00 00", "+2250700000000"),
            ("07.00.00.00.00", "+2250700000000"),
            ("+33 6 12 34 56 78", "+33612345678"),
        ],
    )
    def test_formats_courants(self, saisi, attendu):
        assert normaliser_numero(saisi) == attendu


class TestChoixDuFournisseur:
    def test_numero_ivoirien_passe_par_orange(self):
        assert choisir_fournisseur(NUMERO_CI) == "orange"

    def test_numero_etranger_passe_par_twilio(self):
        assert choisir_fournisseur(NUMERO_ETRANGER) == "twilio"

    def test_numero_ivoirien_bascule_sur_twilio_si_orange_non_configure(self, settings):
        settings.ORANGE_SMS_CLIENT_ID = ""
        assert choisir_fournisseur(NUMERO_CI) == "twilio"

    @pytest.mark.parametrize("force", ["orange", "twilio"])
    def test_fournisseur_force_par_la_configuration(self, settings, force):
        settings.NOTIFICATIONS_SMS_PROVIDER = force
        assert choisir_fournisseur(NUMERO_CI) == force
        assert choisir_fournisseur(NUMERO_ETRANGER) == force


@pytest.mark.django_db
class TestSimulation:
    def test_simulation_trace_le_fournisseur_sans_aucun_appel_reseau(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = True

        with patch("requests.post") as post, patch("twilio.rest.Client") as client:
            log_ci = envoyer_sms(NUMERO_CI, "Bonjour", company=company_a)
            log_etranger = envoyer_sms(NUMERO_ETRANGER, "Bonjour", company=company_a)

        post.assert_not_called()
        client.assert_not_called()
        assert (log_ci.statut, log_ci.fournisseur) == (StatutNotification.SIMULE, "orange")
        assert (log_etranger.statut, log_etranger.fournisseur) == (StatutNotification.SIMULE, "twilio")

    def test_numero_saisi_localement_est_normalise_dans_le_log(self, company_a, settings):
        settings.NOTIFICATIONS_SIMULATION_MODE = True

        log = envoyer_sms("07 00 00 00 00", "Bonjour", company=company_a)

        assert log.destinataire == NUMERO_CI
        assert log.fournisseur == "orange"


@pytest.mark.django_db
class TestOrange:
    def test_envoi_reussi(self, company_a):
        with patch("requests.post", side_effect=[REPONSE_JETON, REPONSE_ENVOI]) as post:
            log = envoyer_sms(NUMERO_CI, "Bonjour Awa", company=company_a)

        assert log.statut == StatutNotification.ENVOYE
        assert log.fournisseur == "orange"
        assert log.reference_fournisseur == "msg-42"
        assert log.erreur == ""

        appel_jeton, appel_envoi = post.call_args_list
        assert appel_jeton.args[0] == "https://api.orange.com/oauth/v3/token"
        assert appel_jeton.kwargs["auth"] == ("orange-id", "orange-secret")
        assert appel_jeton.kwargs["data"] == {"grant_type": "client_credentials"}
        assert appel_envoi.args[0] == (
            f"https://api.orange.com/smsmessaging/v1/outbound/{quote('tel:+2250000', safe='')}/requests"
        )
        assert appel_envoi.kwargs["headers"] == {"Authorization": "Bearer jeton-orange"}
        assert appel_envoi.kwargs["json"] == {
            "outboundSMSMessageRequest": {
                "address": f"tel:{NUMERO_CI}",
                "senderAddress": "tel:+2250000",
                "outboundSMSTextMessage": {"message": "Bonjour Awa"},
            }
        }

    def test_nom_expediteur_optionnel_transmis(self, company_a, settings):
        settings.ORANGE_SMS_SENDER_NAME = "STC Voyages"

        with patch("requests.post", side_effect=[REPONSE_JETON, REPONSE_ENVOI]) as post:
            envoyer_sms(NUMERO_CI, "Bonjour", company=company_a)

        corps = post.call_args_list[1].kwargs["json"]["outboundSMSMessageRequest"]
        assert corps["senderName"] == "STC Voyages"

    def test_le_jeton_est_reutilise_entre_deux_envois(self, company_a):
        with patch("requests.post", side_effect=[REPONSE_JETON, REPONSE_ENVOI, REPONSE_ENVOI]) as post:
            envoyer_sms(NUMERO_CI, "Un", company=company_a)
            envoyer_sms(NUMERO_CI, "Deux", company=company_a)

        urls = [appel.args[0] for appel in post.call_args_list]
        assert urls.count("https://api.orange.com/oauth/v3/token") == 1
        assert cache.get(ORANGE_TOKEN_CACHE_KEY) == "jeton-orange"

    def test_jeton_revoque_redemande_un_jeton_et_reessaie_une_fois(self, company_a):
        cache.set(ORANGE_TOKEN_CACHE_KEY, "vieux-jeton", timeout=600)
        refuse = reponse_http(401, text="token expired")

        with patch("requests.post", side_effect=[refuse, REPONSE_JETON, REPONSE_ENVOI]) as post:
            log = envoyer_sms(NUMERO_CI, "Bonjour", company=company_a)

        assert log.statut == StatutNotification.ENVOYE
        assert post.call_args_list[0].kwargs["headers"] == {"Authorization": "Bearer vieux-jeton"}
        assert post.call_args_list[2].kwargs["headers"] == {"Authorization": "Bearer jeton-orange"}

    def test_erreur_api_est_tracee_en_echec_sans_lever(self, company_a):
        erreur = reponse_http(400, text="invalid address")

        with patch("requests.post", side_effect=[REPONSE_JETON, erreur]):
            log = envoyer_sms(NUMERO_CI, "Bonjour", company=company_a)

        assert log.statut == StatutNotification.ECHEC
        assert "400" in log.erreur and "invalid address" in log.erreur
        assert log.reference_fournisseur == ""

    def test_identifiants_absents_donnent_un_echec_trace(self, company_a, settings):
        settings.NOTIFICATIONS_SMS_PROVIDER = "orange"
        settings.ORANGE_SMS_CLIENT_SECRET = ""

        with patch("requests.post") as post:
            log = envoyer_sms(NUMERO_CI, "Bonjour", company=company_a)

        post.assert_not_called()
        assert log.statut == StatutNotification.ECHEC
        assert "ORANGE_SMS_CLIENT_SECRET" in log.erreur


@pytest.mark.django_db
class TestTwilio:
    def test_envoi_reussi(self, company_a):
        with patch("twilio.rest.Client") as client, patch("requests.post") as post:
            client.return_value.messages.create.return_value.sid = "SM123"
            log = envoyer_sms(NUMERO_ETRANGER, "Hello", company=company_a)

        post.assert_not_called()
        client.assert_called_once_with("ACtest", "token-test")
        client.return_value.messages.create.assert_called_once_with(
            body="Hello", from_="+15005550006", to=NUMERO_ETRANGER
        )
        assert log.statut == StatutNotification.ENVOYE
        assert log.fournisseur == "twilio"
        assert log.reference_fournisseur == "SM123"

    def test_erreur_twilio_est_tracee_en_echec_sans_lever(self, company_a):
        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.side_effect = RuntimeError("numéro invalide")
            log = envoyer_sms(NUMERO_ETRANGER, "Hello", company=company_a)

        assert log.statut == StatutNotification.ECHEC
        assert log.erreur == "numéro invalide"
        assert NotificationLog.objects.count() == 1

    def test_identifiants_absents_donnent_un_echec_trace(self, company_a, settings):
        settings.TWILIO_AUTH_TOKEN = ""

        with patch("twilio.rest.Client") as client:
            log = envoyer_sms(NUMERO_ETRANGER, "Hello", company=company_a)

        client.assert_not_called()
        assert log.statut == StatutNotification.ECHEC
        assert "TWILIO_AUTH_TOKEN" in log.erreur
