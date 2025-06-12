import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import rider_part.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'velocy_verse.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            rider_part.routing.websocket_urlpatterns
        )
    ),
})
