from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import rider_part.routing  # ← replace `yourapp` with your actual app name

application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(
        URLRouter(
            rider_part.routing.websocket_urlpatterns
        )
    ),
})
