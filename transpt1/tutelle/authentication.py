"""Authentification des comptes tutelle : une clé d'API, un système séparé des jetons JWT des comptes internes
(`core.User`). Utilisée seulement là où elle est explicitement déclarée (`FluxEntrantView.authentication_classes`) —
jamais ajoutée à `DEFAULT_AUTHENTICATION_CLASSES` : une clé tutelle n'ouvre l'accès à aucune autre route de l'API, et
un jeton JWT de compte interne (même PDG) n'authentifie jamais un compte tutelle."""

from django.utils import timezone
from rest_framework import authentication, exceptions

from tutelle.models import CompteTutelle

EN_TETE = "Authorization"
PREFIXE = "ApiKey "


class CompteTutelleAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        entete = request.headers.get(EN_TETE, "")
        if not entete.startswith(PREFIXE):
            return None  # aucune clé tutelle présentée : laisse la main (anonyme, refusé ensuite par la permission)
        cle = entete[len(PREFIXE):].strip()
        if not cle:
            raise exceptions.AuthenticationFailed("Clé d'API tutelle manquante.")
        try:
            compte = CompteTutelle.objects.get(cle_hachee=CompteTutelle.hacher(cle))
        except CompteTutelle.DoesNotExist:
            raise exceptions.AuthenticationFailed("Clé d'API tutelle invalide.")
        if not compte.actif:
            raise exceptions.AuthenticationFailed("Ce compte tutelle est désactivé.")
        compte.derniere_utilisation = timezone.now()
        compte.save(update_fields=["derniere_utilisation"])
        return (compte, None)

    def authenticate_header(self, request):
        return PREFIXE.strip()
