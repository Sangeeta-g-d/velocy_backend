# velocy_backend/asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_backend.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from rider_part.middleware import JWTAuthMiddleware
from rider_part.routing import websocket_urlpatterns as rider_ws
from rider_part.consumers import ChatConsumer
from support.routing import websocket_urlpatterns as support_ws

application = ProtocolTypeRouter({
    "http": get_asgi_application(),

    "websocket": URLRouter([
        # Rider/driver chats → require JWT
       re_path(
        r'^ws/chat/(?P<ride_id>\w+)/$',
        JWTAuthMiddleware(ChatConsumer.as_asgi())  # call the middleware instance
        ),


        # Support chats → no JWT (admin panel/session-based)
        *support_ws,
    ]),
})
