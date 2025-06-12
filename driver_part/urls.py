from django.urls import path
from .views import *

urlpatterns = [
    path('toggle-online/', ToggleOnlineStatusAPIView.as_view(), name='toggle-online'),
    path('cash-limit/', DriverCashLimitAPIView.as_view(), name='driver-cash-limit'),
    path('available-now-rides/', AvailableNowRidesAPIView.as_view(), name='available-now-rides'),
    path('available-scheduled-rides/', AvailableScheduledRidesAPIView.as_view(), name='available_scheduled_rides'),
    path('ride-details/<int:ride_id>/', RideRequestDetailAPIView.as_view(), name='ride-request-detail'),
    
    path('decline-ride/',DeclineRideAPIView.as_view(),name='decline-ride'),
    path('accept-ride/<int:ride_id>/',AcceptRideAPIView.as_view(),name="accept-ride"),
    path('cancel-ride/<int:ride_id>/',CancelRideAPIView.as_view(),name="cancel-ride"),

    # 12-6-25
    path('pick-up-navigation/<int:ride_id>/', RideDetailAPIView.as_view(), name='ride-detail'),
    path('drop-navigation/<int:ride_id>/', RideDetailView.as_view(), name='ride-detail'),
    path('begin-ride/<int:ride_id>/', SetRideStartTimeAPIView.as_view(), name='ride-start-time'),
    path('complete-ride/<int:ride_id>/', SetRideEndTimeAPIView.as_view(), name='ride-end-time'),
    
]