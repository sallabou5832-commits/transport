"""Carte temps réel : authentification et permission du canal WebSocket (`dashboard/ws_auth.py`,
`dashboard/consumers.py`), et réception effective d'une position envoyée par un vrai conducteur via
l'API HTTP (`personnel_roulant.suivi.diffuser_position`, appelé par `PositionViewSet.create`).

`transaction=True` : le consommateur touche la base depuis un autre thread (`channels.db`), invisible à la
transaction habituelle de `@pytest.mark.django_db`. Channel layer vidée entre les tests (voir
`channel_layer_vide`) : sans cela, un groupe d'une compagnie dont l'identifiant est réutilisé d'un test à
l'autre (base rejouée à chaque test) pourrait encore contenir un canal du test précédent."""

import asyncio
import datetime
import json

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.models import Role
from dashboard.routing import websocket_urlpatterns
from dashboard.ws_auth import JWTAuthMiddleware
from personnel_roulant.tests.conftest_suivi import equipe, trajet  # noqa: F401

APPLICATION = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


@pytest.fixture(autouse=True)
def channel_layer_vide():
    from channels.layers import get_channel_layer

    yield
    couche = get_channel_layer()
    if couche is not None:
        asyncio.run(couche.flush())


def _jeton(utilisateur):
    return str(AccessToken.for_user(utilisateur))


async def _tenter_connexion(jeton=None):
    chemin = "/ws/dashboard/carte/" + (f"?token={jeton}" if jeton else "")
    communicator = WebsocketCommunicator(APPLICATION, chemin)
    connecte, _ = await communicator.connect()
    return communicator, connecte


def _executer(coroutine):
    return asyncio.run(coroutine())


@pytest.mark.django_db(transaction=True)
class TestAuthentificationEtPermission:
    def test_sans_jeton_la_connexion_est_refusee(self):
        async def scenario():
            _, connecte = await _tenter_connexion()
            assert not connecte

        _executer(scenario)

    def test_jeton_invalide_est_refuse(self):
        async def scenario():
            _, connecte = await _tenter_connexion("nimportequoi")
            assert not connecte

        _executer(scenario)

    def test_role_sans_droit_sur_la_carte_est_refuse(self, equipe):  # noqa: F811
        async def scenario():
            _, connecte = await _tenter_connexion(_jeton(equipe["guichetier"]))
            assert not connecte

        _executer(scenario)

    def test_qhse_de_la_compagnie_est_accepte(self, equipe):  # noqa: F811
        async def scenario():
            communicator, connecte = await _tenter_connexion(_jeton(equipe["qhse"]))
            assert connecte
            await communicator.disconnect()

        _executer(scenario)

    def test_superadmin_sans_compagnie_est_refuse(self, user_factory):
        superadmin = user_factory("superadmin_carte", Role.SUPERADMIN, company=None)

        async def scenario():
            _, connecte = await _tenter_connexion(_jeton(superadmin))
            assert not connecte

        _executer(scenario)

    def test_compte_suspendu_est_refuse(self, equipe):  # noqa: F811
        jeton = _jeton(equipe["qhse"])
        equipe["qhse"].is_active = False
        equipe["qhse"].save(update_fields=["is_active"])

        async def scenario():
            _, connecte = await _tenter_connexion(jeton)
            assert not connecte

        _executer(scenario)


@pytest.mark.django_db(transaction=True)
class TestDiffusion:
    def _poster(self, utilisateur, donnees):
        from channels.db import database_sync_to_async

        def appel():
            client = APIClient()
            client.force_authenticate(user=utilisateur)
            return client.post("/api/positions/", donnees, format="json")

        return database_sync_to_async(appel)()

    def test_une_position_envoyee_est_recue_par_qui_regarde_la_carte(self, equipe, trajet):  # noqa: F811
        async def scenario():
            communicator, connecte = await _tenter_connexion(_jeton(equipe["qhse"]))
            assert connecte

            reponse = await self._poster(
                equipe["conducteur"], {"latitude": "5.812345", "longitude": "-4.512345", "vitesse_kmh": 72}
            )
            assert reponse.status_code == 201

            message = await communicator.receive_from()
            position = json.loads(message)
            assert position["vehicule"] == trajet["vehicule"].id
            assert position["immatriculation"] == trajet["vehicule"].immatriculation
            assert position["vitesse_kmh"] == 72
            assert position["en_direct"] is True

            await communicator.disconnect()

        _executer(scenario)

    def test_un_lot_en_retard_diffuse_la_position_la_plus_recente_pas_la_derniere_de_la_liste(self, equipe, trajet):  # noqa: F811
        maintenant = timezone.now()
        lot = [
            {"latitude": "5.81", "longitude": "-4.51", "vitesse_kmh": 90, "releve_le": (maintenant - datetime.timedelta(minutes=1)).isoformat()},
            {"latitude": "5.82", "longitude": "-4.52", "vitesse_kmh": 40, "releve_le": (maintenant - datetime.timedelta(minutes=10)).isoformat()},
        ]

        async def scenario():
            communicator, connecte = await _tenter_connexion(_jeton(equipe["qhse"]))
            assert connecte

            reponse = await self._poster(equipe["conducteur"], lot)
            assert reponse.status_code == 201

            position = json.loads(await communicator.receive_from())
            assert position["vitesse_kmh"] == 90  # le relevé le plus récent, pas le dernier envoyé dans le lot

            await communicator.disconnect()

        _executer(scenario)

    def test_une_autre_compagnie_ne_recoit_rien(self, equipe, trajet, user_factory, company_b):  # noqa: F811
        qhse_b = user_factory("qhse_b_carte", Role.QHSE, company=company_b)

        async def scenario():
            communicator, connecte = await _tenter_connexion(_jeton(qhse_b))
            assert connecte

            reponse = await self._poster(
                equipe["conducteur"], {"latitude": "5.81", "longitude": "-4.51", "vitesse_kmh": 50}
            )
            assert reponse.status_code == 201

            recu = await communicator.receive_nothing(timeout=0.2)
            assert recu is True  # rien n'est arrivé : la compagnie B ne voit pas les cars de la compagnie A

            await communicator.disconnect()

        _executer(scenario)
