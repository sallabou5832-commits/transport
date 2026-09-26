from django.urls import re_path

from dashboard.consumers import CarteConsumer

websocket_urlpatterns = [
    re_path(r'^ws/dashboard/carte/$', CarteConsumer.as_asgi()),
]
