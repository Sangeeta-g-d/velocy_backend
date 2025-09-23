# velocy_backend/asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_backend.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from rider_part.middleware import JWTAuthMiddleware
from rider_part.routing import websocket_urlpatterns as rider_ws
from support.routing import websocket_urlpatterns as support_ws

# Apply JWT middleware to all rider WebSocket routes
authenticated_rider_ws = JWTAuthMiddleware(URLRouter(rider_ws))

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter([
        # Rider/driver WebSockets → require JWT
        *authenticated_rider_ws,
        
        # Support chats → no JWT (admin panel/session-based)
        *support_ws,
    ]),
})