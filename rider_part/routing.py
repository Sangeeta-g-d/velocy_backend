from django.urls import re_path
from .consumers import *

websocket_urlpatterns = [
    re_path(r'ws/ride-tracking/(?P<ride_id>\d+)/$', RideTrackingConsumer.as_asgi()),
    re_path(r'ws/rider/otp/$', RideNotificationConsumer.as_asgi()),
    re_path(r'ws/chat/(?P<ride_id>\w+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/payment/status/(?P<ride_id>\d+)/$', RidePaymentStatusConsumer.as_asgi()),
    re_path(r'^ws/rider/notifications/$', RideAcceptanceConsumer.as_asgi()),

    # shared live tracking for both rider and driver
    re_path(r'ws/shared_ride_tracking/<int:ride_id>/', SharedRideTrackingConsumer.as_asgi())
]
