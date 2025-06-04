from django.urls import path
from .views import *

urlpatterns = [
    path('toggle-online/', ToggleOnlineStatusAPIView.as_view(), name='toggle-online'),
    path('cash-limit/', DriverCashLimitAPIView.as_view(), name='driver-cash-limit'),
    path('available-now-rides/', AvailableNowRidesAPIView.as_view(), name='available-now-rides'),
    path('available-scheduled-rides/', AvailableScheduledRidesAPIView.as_view(), name='available_scheduled_rides'),
    path('ride-details/<int:ride_id>/', RideRequestDetailAPIView.as_view(), name='ride-request-detail'),
]