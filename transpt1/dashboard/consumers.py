"""Carte temps réel : `GET /api/dashboard/carte/` (HTTP) donne l'état complet au premier chargement,
ce canal ne pousse ensuite que les positions qui bougent (voir `personnel_roulant.suivi.diffuser_position`,
appelé par `PositionViewSet.create`). Le HTTP reste la seule source pour la liste des cars en route :
un message poussé ne fait jamais apparaître ou disparaître un car, seulement rafraîchir sa position
(voir `frontend/src/lib/carte.js`, `fusionnerPositions`)."""

import json
from types import SimpleNamespace

from channels.generic.websocket import AsyncWebsocketConsumer

from dashboard.permissions import PeutVoirLaCarte


class CarteConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        utilisateur = self.scope['user']
        if not self._peut_voir(utilisateur):
            await self.close(code=4403)
            return
        self.groupe = f'carte_{utilisateur.company_id}'
        await self.channel_layer.group_add(self.groupe, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'groupe'):
            await self.channel_layer.group_discard(self.groupe, self.channel_name)

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
