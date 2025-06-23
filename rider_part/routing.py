from django.urls import re_path
from .consumers import RideTrackingConsumer,RideNotificationConsumer,ChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/ride-tracking/(?P<ride_id>\d+)/$', RideTrackingConsumer.as_asgi()),
    re_path(r'ws/rider/otp/$', RideNotificationConsumer.as_asgi()),
    re_path(r'ws/chat/(?P<ride_id>\w+)/$', ChatConsumer.as_asgi()),
]
