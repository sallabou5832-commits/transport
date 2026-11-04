"""Carte temps réel : `GET /api/dashboard/carte/` (HTTP) donne l'état complet au premier chargement,
ce canal ne pousse ensuite que les positions qui bougent (voir `personnel_roulant.suivi.diffuser_position`,
appelé par `PositionViewSet.create`). Le HTTP reste la seule source pour la liste des cars en route :
un message poussé ne fait jamais apparaître ou disparaître un car, seulement rafraîchir sa position
(voir `frontend/src/lib/carte.js`, `fusionnerPositions`)."""

import asyncio
import json
import logging
import time
from types import SimpleNamespace

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from dashboard.permissions import PeutVoirLaCarte
from dashboard.ws_auth import recharger_utilisateur

logger = logging.getLogger(__name__)

# Code de fermeture : session plus valable (compte suspendu, droit retiré, jeton expiré). Le site renouvelle son jeton avant
# de se reconnecter (`frontend/src/api/useFluxCarte.js`). 4403 reste le refus à l'ouverture.
CODE_SESSION_TERMINEE = 4401


class CarteConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        utilisateur = self.scope['user']
        if not self._peut_voir(utilisateur):
            await self.close(code=4403)
            return
        self.groupe = f'carte_{utilisateur.company_id}'
        await self.channel_layer.group_add(self.groupe, self.channel_name)
        await self.accept()
        self._surveillance = asyncio.create_task(self._surveiller(utilisateur.pk))

    async def disconnect(self, code):
        surveillance = getattr(self, '_surveillance', None)
        if surveillance is not None:
            surveillance.cancel()
        if hasattr(self, 'groupe'):
            await self.channel_layer.group_discard(self.groupe, self.channel_name)

    async def _surveiller(self, identifiant):
        """Une connexion WebSocket survit au jeton qui l'a ouverte : sans ce contrôle, un compte suspendu par le PDG (ou un
        jeton expiré, ou une session fermée) continuerait de recevoir les positions des cars tant que le navigateur reste
        ouvert."""
        while True:
            await asyncio.sleep(settings.CARTE_REVALIDATION_SECONDES)
            echeance = self.scope.get('jeton_expire_le')
            if echeance is not None and time.time() >= echeance:
                break
            try:
                utilisateur = await recharger_utilisateur(identifiant)
            except Exception:  # noqa: BLE001
                # Une base momentanément indisponible ne doit ni couper la carte de tout le monde ni arrêter la
                # surveillance en silence : on réessaie au prochain contrôle.
                logger.exception('Carte : relecture du compte %s impossible, nouvel essai au prochain contrôle', identifiant)
                continue
            if not self._peut_voir(utilisateur) or utilisateur.version_session != self.scope.get('version_session'):
                break  # compte suspendu, droits retirés, ou session fermée (mot de passe changé...)
        await self.close(code=CODE_SESSION_TERMINEE)

    async def receive(self, text_data=None, bytes_data=None):
        return  # Rien n'est attendu du navigateur ici : la position se poste en HTTP, pas sur ce canal.

    async def position(self, event):
        """Un message de groupe envoyé par `personnel_roulant.suivi.diffuser_position` : renvoyé tel
        quel au navigateur, même forme qu'une entrée de `GET /api/dashboard/carte/`."""
        await self.send(text_data=json.dumps(event['position']))

    def _peut_voir(self, utilisateur):
        # Même règle que la route HTTP (`PeutVoirLaCarte`), pour qu'aucun rôle n'ait accès ici sans
        # l'avoir en HTTP, ni l'inverse : `has_permission` ne lit que `request.user`.
        return bool(utilisateur and utilisateur.is_authenticated) and PeutVoirLaCarte().has_permission(
            SimpleNamespace(user=utilisateur), None
        )
