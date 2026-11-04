"""Authentification par jeton JWT qui refuse aussi les sessions fermées (`core.sessions`) : un jeton d'accès émis avant un
changement de mot de passe ou un « déconnecter mes autres appareils » ne vaut plus, sans attendre son expiration.

Un compte au mot de passe provisoire (créé ou réinitialisé par le PDG ou le DRH) ne fait rien d'autre que se connaître et
changer ce mot de passe : celui qui l'a créé le connaît, il ne doit pas pouvoir s'en servir."""

from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.sessions import verifier_version

CHEMINS_MOT_DE_PASSE_PROVISOIRE = {"/api/auth/me/", "/api/auth/mot-de-passe/", "/api/configuration/moi/"}


class JWTAuthentificationSession(JWTAuthentication):
    def authenticate(self, request):
        resultat = super().authenticate(request)
        if resultat is not None and resultat[0].doit_changer_mot_de_passe and request.path not in CHEMINS_MOT_DE_PASSE_PROVISOIRE:
            raise PermissionDenied("Mot de passe provisoire : choisissez le vôtre avant de continuer (Mes paramètres).")
        return resultat

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        verifier_version(user, validated_token)
        return user
