"""
ASGI application para IAGLOBAL
===============================
Integra Django + Channels + ReactPy
"""

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.http import AsgiHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iaglobal.settings')

django.setup()

# Routes para ReactPy
from iaglobal.ui.urls import urlpatterns

application = ProtocolTypeRouter({
    "http": AsgiHandler(),
    "websocket": URLRouter(urlpatterns),
})