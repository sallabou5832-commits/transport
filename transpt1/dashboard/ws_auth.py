"""Authentification des WebSocket : Channels ne passe pas par DRF ni par `JWTAuthentication`
(`core`/`REST_FRAMEWORK`). Le jeton d'accès est lu dans l'URL (`?token=...`), un navigateur ne pouvant
pas poser d'en-tête `Authorization` sur une connexion WebSocket (voir `frontend/src/api/useFluxCarte.js`).

Un jeton absent, invalide, expiré, ou dont le compte a été suspendu depuis (`is_active=False`) laisse
`scope['user']` anonyme : chaque consommateur refuse alors la connexion lui-même (voir
`dashboard/consumers.py`), exactement comme une route DRF refuserait un utilisateur non authentifié.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _utilisateur_du_jeton(jeton):
    from django.contrib.auth import get_user_model

    utilisateur_model = get_user_model()
    try:
        valide = AccessToken(jeton)
        return utilisateur_model.objects.get(pk=valide['user_id'], is_active=True)
    except (TokenError, KeyError, utilisateur_model.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        jetons = parse_qs(scope.get('query_string', b'').decode()).get('token')
        scope['user'] = await _utilisateur_du_jeton(jetons[0]) if jetons else AnonymousUser()
        return await super().__call__(scope, receive, send)
