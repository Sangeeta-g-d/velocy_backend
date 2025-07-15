import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_backend.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from rider_part.middleware import JWTAuthMiddleware
from rider_part.routing import websocket_urlpatterns
from django.urls import re_path
from rider_part.consumers import ChatConsumer

application = ProtocolTypeRouter({
    "http": get_asgi_application(),

    "websocket": JWTAuthMiddleware(
        URLRouter([
            re_path(r'^ws/chat/(?P<ride_id>\w+)/$', ChatConsumer.as_asgi()),
            *websocket_urlpatterns,
        ])
    ),
})
