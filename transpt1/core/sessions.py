"""Durée des sessions et fermeture des sessions ouvertes (accès aux comptes).

Une session, c'est un jeton de renouvellement (`refresh`) : tant qu'il vaut, le site et le mobile obtiennent un nouveau jeton
d'accès (30 min) sans redemander le mot de passe. Sa durée se choisit à la connexion (« rester connecté », `DureeSession`),
sans dépasser le plafond de la compagnie, réduit éventuellement pour le poste (`configuration.services.politique_session`).
Sans choix : 1 jour, comme avant.

Deux revendications s'ajoutent au jeton et passent au jeton d'accès qui en est tiré :
- `vs`, la version de session du compte (`User.version_session`) : l'augmenter ferme d'un coup toutes les sessions ouvertes,
  y compris la carte en temps réel (`dashboard/ws_auth.py`). Un jeton sans `vs` (émis avant) vaut la version 0 ;
- `duree`, la durée accordée, pour rendre une session de même durée à l'appareil qui vient de changer son mot de passe.

Le plafond vaut aussi pour les sessions déjà ouvertes : abaissé par le PDG, il refuse au renouvellement suivant toute session
ouverte depuis plus longtemps que lui.
"""

import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from configuration import regles
from configuration.regles import DureeSession
from configuration.services import politique_session

VERSION = "vs"
DUREE = "duree"


def duree_accordee(user, demandee=None):
    """La durée demandée (1 jour sans demande), ramenée au plafond qui s'applique à cet agent."""
    return regles.plafonner(demandee or DureeSession.PAR_DEFAUT, politique_session(user)["duree_max"], DureeSession.ORDRE)


def _jetons(refresh, duree):
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "duree_session": duree,
        "session_expire_le": refresh["exp"],
    }


def _nouveau_jeton(user, duree):
    refresh = RefreshToken.for_user(user)
    refresh[VERSION] = user.version_session
    refresh[DUREE] = duree
    return refresh


def ouvrir_session(user, demandee=None):
    """Les jetons d'une nouvelle session : `access`, `refresh`, `duree_session` (accordée) et `session_expire_le` (secondes
    Unix)."""
    duree = duree_accordee(user, demandee)
    refresh = _nouveau_jeton(user, duree)
    refresh.set_exp(lifetime=DureeSession.DUREES[duree])
    return _jetons(refresh, duree)


def garder_session(user, ancienne):
    """Les jetons rendus à l'appareil qui vient de fermer les autres sessions : même ouverture et même échéance qu'avant, une
    session ne se prolonge pas sans le mot de passe."""
    duree = ancienne.get(DUREE, DureeSession.PAR_DEFAUT)
    refresh = _nouveau_jeton(user, duree)
    refresh["iat"], refresh["exp"] = ancienne["iat"], ancienne["exp"]
    return _jetons(refresh, duree)


def fermer_les_sessions(user):
    """Toutes les sessions ouvertes de ce compte deviennent invalides (jetons d'accès compris, à la requête suivante)."""
    user.version_session += 1
    user.save(update_fields=["version_session"])


def session_envoyee(user, brut):
    """Le jeton de renouvellement de cet appareil, envoyé dans le corps de la requête ; `None` s'il est absent, invalide,
    expiré, d'un autre compte ou d'une session déjà fermée."""
    if not brut or not isinstance(brut, str):
        return None
    try:
        jeton = RefreshToken(brut)
    except TokenError:
        return None
    if str(jeton.get("user_id")) != str(user.pk) or jeton.get(VERSION, 0) != user.version_session:
        return None
    return jeton


def verifier_version(user, jeton):
    if jeton.get(VERSION, 0) != user.version_session:
        raise AuthenticationFailed("Session fermée : reconnectez-vous.", code="session_fermee")


def verifier_plafond(user, refresh):
    plafond = DureeSession.DUREES[politique_session(user)["duree_max"]]
    if time.time() > refresh.get("iat", 0) + plafond.total_seconds():
        raise AuthenticationFailed(
            "Votre compagnie a raccourci la durée des sessions : reconnectez-vous.", code="session_plafonnee"
        )


class ConnexionSerializer(TokenObtainSerializer):
    """Identifiant, mot de passe et, au choix, `duree_session` (« rester connecté »)."""

    duree_session = serializers.ChoiceField(choices=DureeSession.CHOIX, required=False)

    def validate(self, attrs):
        super().validate(attrs)  # authentifie : lève AuthenticationFailed si les identifiants sont refusés
        update_last_login(None, self.user)  # « dernière connexion » de l'écran Personnel et comptes
        return ouvrir_session(self.user, attrs.get("duree_session"))


class RenouvellementSerializer(TokenRefreshSerializer):
    """Un nouveau jeton d'accès, tant que la session vaut : compte actif, session pas fermée, plafond actuel respecté."""

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])  # TokenError (jeton invalide ou expiré) : 401 par la vue
        user = get_user_model().objects.filter(pk=refresh.get("user_id")).first()
        if user is None or not user.is_active:
            raise AuthenticationFailed(self.error_messages["no_active_account"], "no_active_account")
        verifier_version(user, refresh)
        verifier_plafond(user, refresh)
        return {"access": str(refresh.access_token)}
