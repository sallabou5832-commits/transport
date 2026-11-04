"""Gestionnaire d'exceptions de l'API : ce que DRF ne traduit pas lui-même, et qui finissait en erreur 500.

- `ProtectedError` / `RestrictedError` : on supprime un élément que d'autres données référencent encore (une gare d'une
  ligne, un départ contrôlé, une obligation de formation déjà suivie…). C'est un conflit (409) avec un message clair.
- `OverflowError` : un nombre JSON démesuré (`1e400`) donné à un champ qui attend un identifiant ou un entier, que
  `int()` refuse. C'est une valeur invalide (400).
- `ValueError` « NUL (0x00) » : un caractère nul (`%00` dans l'URL, `\\u0000` dans le JSON) que PostgreSQL refuse de
  stocker ou de comparer. C'est une valeur invalide (400).

Une exception de DRF qui porte un `code_pour_le_client` le donne aussi dans la réponse (`"code"`), à côté du message :
un client ne lit pas le texte, qui peut changer, pour savoir quoi faire d'un refus (voir `core.authentification`).
"""

from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as gestionnaire_drf


def gestionnaire_exceptions(exc, context):
    reponse = gestionnaire_drf(exc, context)
    if reponse is not None:
        code = getattr(exc, "code_pour_le_client", None)
        if code is not None and isinstance(reponse.data, dict):
            reponse.data["code"] = code
        return reponse
    if isinstance(exc, (ProtectedError, RestrictedError)):
        return Response(
            {"detail": "Suppression impossible : cet élément est encore utilisé par d'autres données."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, OverflowError):
        return Response({"detail": "Valeur numérique démesurée."}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ValueError) and "NUL (0x00)" in str(exc):
        return Response({"detail": "Les caractères nuls ne sont pas admis."}, status=status.HTTP_400_BAD_REQUEST)
    return None
