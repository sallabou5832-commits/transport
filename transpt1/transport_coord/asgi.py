"""
ASGI config for transport_coord project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/

Sert le HTTP (Django, DRF) **et** les WebSocket (`channels`, carte temps réel — voir
`dashboard/routing.py`) depuis le même processus : en production, remplacer le serveur WSGI
(gunicorn/waitress) par un serveur ASGI (`daphne transport_coord.asgi:application`), voir
DEPLOIEMENT.md.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'transport_coord.settings')

# Avant d'importer nos routes : elles importent des modèles, qui exigent que Django soit prêt.
django_asgi_app = get_asgi_application()

from dashboard.routing import websocket_urlpatterns  # noqa: E402
from dashboard.ws_auth import JWTAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        'websocket': JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
