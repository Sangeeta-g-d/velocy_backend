from django.urls import re_path
from .consumers import *
# from .consumers import SharedRideTrackingConsumer

websocket_urlpatterns = [
    re_path(r'ws/ride-tracking/(?P<ride_id>\d+)/$', RideTrackingConsumer.as_asgi()),
    # driver arrival notification
    re_path(r'ws/driver_arrival/(?P<ride_id>\d+)/$', RideRequestConsumer.as_asgi()),
    re_path(r'ws/rider/otp/(?P<ride_id>\d+)/$', RideNotificationConsumer.as_asgi()),
    re_path(r'ws/chat/(?P<ride_id>\w+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/payment/status/(?P<ride_type>normal|shared)/(?P<ride_id>\d+)/$', RidePaymentStatusConsumer.as_asgi()),
    re_path(r'^ws/rider/notifications/(?P<user_id>\d+)/$', RideAcceptanceConsumer.as_asgi()),
    re_path(r'^ws/rider/notifications/$', RideAcceptanceConsumer.as_asgi()),
    # shared live tracking for both rider and driver
    re_path(r'ws/shared_ride_tracking/(?P<ride_id>\d+)/$', SharedRideTrackingConsumer.as_asgi()),
    re_path(r'ws/shared-ride-notifications/$', SharedRideNotificationConsumer.as_asgi()),

    # ride completion consumer
    re_path(r'ws/ride/completion/(?P<ride_id>\d+)/$', RideCompletionConsumer.as_asgi()),
]
