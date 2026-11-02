"""Authentification du logiciel de billetterie d'une compagnie : `Authorization: ApiKey <clé>`, une clé créée par le PDG ou le
directeur des opérations. Déclarée seulement sur les routes du lien (`authentication_classes` de ses vues), jamais dans
`DEFAULT_AUTHENTICATION_CLASSES` : la clé n'ouvre aucune autre route de l'API, et un jeton JWT d'un agent n'ouvre pas le lien."""

from django.utils import timezone
from rest_framework import authentication, exceptions

from lien_billetterie.models import CleLienBilletterie

PREFIXE = "ApiKey "


class CleLienAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        entete = request.headers.get("Authorization", "")
        if not entete.startswith(PREFIXE):
            return None  # aucune clé présentée : refusé ensuite par la permission (401)
        cle = entete[len(PREFIXE):].strip()
        if not cle:
            raise exceptions.AuthenticationFailed("Clé d'API du lien de billetterie manquante.")
        compte = CleLienBilletterie.objects.select_related("company").filter(cle_hachee=CleLienBilletterie.hacher(cle)).first()
        if compte is None:
            raise exceptions.AuthenticationFailed("Clé d'API du lien de billetterie invalide.")
        if not compte.active:
            raise exceptions.AuthenticationFailed("Cette clé a été révoquée par la compagnie.")
        # Sans passer par save() : ce n'est pas une modification de la clé à tracer dans le journal d'audit.
        CleLienBilletterie.objects.filter(pk=compte.pk).update(derniere_utilisation=timezone.now())
        return (compte, None)

    def authenticate_header(self, request):
        return PREFIXE.strip()
