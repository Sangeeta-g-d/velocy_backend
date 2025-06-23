import os
import django

# ✅ Set DJANGO_SETTINGS_MODULE early
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_backend.settings')

# ✅ Initialize Django before importing models or consumers
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from rider_part.middleware import JWTAuthMiddleware  # Custom middleware
from rider_part.routing import websocket_urlpatterns  # Other WebSocket URLs

# Optional: Use re_path if needed for inline routes
from django.urls import re_path
from rider_part.consumers import ChatConsumer  # Secure chat consumer

application = ProtocolTypeRouter({
    "http": get_asgi_application(),

    # ✅ WebSocket handler
    "websocket": JWTAuthMiddleware(
        URLRouter([
            # Main chat route secured with JWT token in query string
            re_path(r'^ws/chat/(?P<ride_id>\w+)/$', ChatConsumer.as_asgi()),

            # ✅ Include other WebSocket consumers (ride-tracking, etc.)
            *websocket_urlpatterns,
        ])
    ),
})
