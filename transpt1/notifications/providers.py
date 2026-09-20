"""Fournisseurs de messages : SMS via Orange (Côte d'Ivoire) ou Twilio, WhatsApp via Twilio.

Chaque fonction ``envoyer_via_*`` retourne la référence du message côté
fournisseur, ou lève une exception en cas d'échec. Aucune n'est appelée en mode
simulation (voir ``notifications.services.envoyer_sms``).
"""

import json
import re
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache

FOURNISSEUR_ORANGE = "orange"
FOURNISSEUR_TWILIO = "twilio"

ORANGE_API_URL = "https://api.orange.com"
ORANGE_TOKEN_CACHE_KEY = "notifications:orange:access_token"
ORANGE_TIMEOUT_SECONDES = 10
# Marge avant l'expiration réelle du jeton pour ne jamais en utiliser un périmé.
ORANGE_TOKEN_MARGE_SECONDES = 300

PREFIXE_COTE_D_IVOIRE = "+225"


class ErreurFournisseur(Exception):
    """Échec d'envoi côté fournisseur (configuration manquante, API en erreur...)."""


def normaliser_numero(numero):
    """Met un numéro au format international E.164 (``+2250700000000``).

    Le champ ``passager_telephone`` est libre : on accepte les espaces, points
    et tirets, le préfixe ``00`` et les numéros ivoiriens à 10 chiffres saisis
    sans indicatif (``07 00 00 00 00``).
    """
    numero = re.sub(r"[\s.\-()]", "", numero or "")
    if numero.startswith("00"):
        numero = "+" + numero[2:]
    elif re.fullmatch(r"0\d{9}", numero):
        numero = PREFIXE_COTE_D_IVOIRE + numero
    return numero


def orange_est_configure():
    return bool(settings.ORANGE_SMS_CLIENT_ID and settings.ORANGE_SMS_CLIENT_SECRET and settings.ORANGE_SMS_SENDER)


def choisir_fournisseur(numero):
    """Détermine le fournisseur à utiliser pour un numéro déjà normalisé.

    ``NOTIFICATIONS_SMS_PROVIDER`` peut forcer ``orange`` ou ``twilio``. En mode
    ``auto`` (défaut), les numéros ivoiriens passent par Orange (tarif local) dès
    qu'il est configuré, tout le reste par Twilio.
    """
    choix = settings.NOTIFICATIONS_SMS_PROVIDER
    if choix in (FOURNISSEUR_ORANGE, FOURNISSEUR_TWILIO):
        return choix
    if numero.startswith(PREFIXE_COTE_D_IVOIRE) and orange_est_configure():
        return FOURNISSEUR_ORANGE
    return FOURNISSEUR_TWILIO


def _client_twilio(expediteur, nom_variable_expediteur):
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and expediteur):
        raise ErreurFournisseur(
            "Twilio n'est pas configuré "
            f"(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, {nom_variable_expediteur})."
        )
    from twilio.rest import Client

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def envoyer_via_twilio(destinataire, contenu):
    client = _client_twilio(settings.TWILIO_FROM_NUMBER, "TWILIO_FROM_NUMBER")
    message = client.messages.create(body=contenu, from_=settings.TWILIO_FROM_NUMBER, to=destinataire)
    return message.sid


def envoyer_whatsapp_via_twilio(destinataire, contenu, variables=None):
    """Envoie un message WhatsApp via Twilio.

    WhatsApp n'autorise un message libre (``contenu``) que dans les 24 h suivant
    un message du client, ou dans le bac à sable Twilio après son opt-in. Un
    message à l'initiative de l'entreprise (confirmation de billet) exige un modèle
    approuvé par WhatsApp : si ``TWILIO_WHATSAPP_CONTENT_SID`` est renseigné et que
    des ``variables`` sont fournies, le modèle est utilisé (variables ``{{1}}``,
    ``{{2}}``...) à la place du texte libre.
    """
    client = _client_twilio(settings.TWILIO_WHATSAPP_FROM, "TWILIO_WHATSAPP_FROM")
    parametres = {
        "from_": f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
        "to": f"whatsapp:{destinataire}",
    }
    if settings.TWILIO_WHATSAPP_CONTENT_SID and variables:
        parametres["content_sid"] = settings.TWILIO_WHATSAPP_CONTENT_SID
        parametres["content_variables"] = json.dumps(variables)
    else:
        parametres["body"] = contenu
    return client.messages.create(**parametres).sid


def _orange_jeton(*, forcer=False):
    """Retourne un jeton OAuth2 Orange (client credentials), mis en cache."""
    import requests

    if not forcer:
        jeton = cache.get(ORANGE_TOKEN_CACHE_KEY)
        if jeton:
            return jeton

    reponse = requests.post(
        f"{ORANGE_API_URL}/oauth/v3/token",
        auth=(settings.ORANGE_SMS_CLIENT_ID, settings.ORANGE_SMS_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=ORANGE_TIMEOUT_SECONDES,
    )
    reponse.raise_for_status()
    donnees = reponse.json()
    jeton = donnees["access_token"]
    duree = max(int(donnees.get("expires_in", 3600)) - ORANGE_TOKEN_MARGE_SECONDES, 60)
    cache.set(ORANGE_TOKEN_CACHE_KEY, jeton, timeout=duree)
    return jeton


def envoyer_via_orange(destinataire, contenu):
    if not orange_est_configure():
        raise ErreurFournisseur(
            "Orange SMS n'est pas configuré "
            "(ORANGE_SMS_CLIENT_ID, ORANGE_SMS_CLIENT_SECRET, ORANGE_SMS_SENDER)."
        )
    import requests

    sender = f"tel:{settings.ORANGE_SMS_SENDER}"
    corps = {
        "outboundSMSMessageRequest": {
            "address": f"tel:{destinataire}",
            "senderAddress": sender,
            "outboundSMSTextMessage": {"message": contenu},
        }
    }
    if settings.ORANGE_SMS_SENDER_NAME:
        corps["outboundSMSMessageRequest"]["senderName"] = settings.ORANGE_SMS_SENDER_NAME
    url = f"{ORANGE_API_URL}/smsmessaging/v1/outbound/{quote(sender, safe='')}/requests"

    reponse = None
    for forcer_jeton in (False, True):
        reponse = requests.post(
            url,
            json=corps,
            headers={"Authorization": f"Bearer {_orange_jeton(forcer=forcer_jeton)}"},
            timeout=ORANGE_TIMEOUT_SECONDES,
        )
        if reponse.status_code != 401:
            break  # 401 : jeton révoqué avant son expiration, on en redemande un une fois.

    if not reponse.ok:
        raise ErreurFournisseur(f"Orange SMS a répondu {reponse.status_code} : {reponse.text[:300]}")

    resource_url = reponse.json().get("outboundSMSMessageRequest", {}).get("resourceURL", "")
    return resource_url.rstrip("/").rsplit("/", 1)[-1]
