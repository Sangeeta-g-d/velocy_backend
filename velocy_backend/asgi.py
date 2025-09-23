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
from rider_part.consumers import ChatConsumer, RidePaymentStatusConsumer
from support.routing import websocket_urlpatterns as support_ws

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter([
        # Apply JWT middleware to specific routes that need authentication
        re_path(
            r'^ws/chat/(?P<ride_id>\w+)/$',
            JWTAuthMiddleware(ChatConsumer.as_asgi())
        ),
        re_path(
            r'^ws/payment/status/(?P<ride_type>normal|shared)/(?P<ride_id>\d+)/$',
            JWTAuthMiddleware(RidePaymentStatusConsumer.as_asgi())
        ),
        
        # Include other rider routes (apply middleware to them individually if needed)
        *rider_ws,
        
        # Support chats → no JWT (admin panel/session-based)
        *support_ws,
    ]),
})