from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
from . import serializers

urlpatterns = [
    path('add-vehicle/', AddRideShareVehicleAPIView.as_view(), name='add_ride_share_vehicle'),
    path('my-vehicles/', GetRideShareVehicleAPIView.as_view(), name='get_my_vehicles'),
    path('create-trip/<int:vehicle_id>/', CreateRideAPIView.as_view(), name='create_ride'),
    path('upcoming-trips/', UpcomingRidesAPIView.as_view(), name='my_upcoming_rides'),
    path('available-trips/', PublicRidesListAPIView.as_view(), name='available_rides'),
    path('join-trip/<int:ride_id>/', JoinRideAPIView.as_view(), name='join_ride'),
    path('trip-requests/<int:ride_id>/', RideJoinRequestsAPIView.as_view(), name='ride_join_requests'),
    path('join-requests/',UserRequestedRidesAPIView.as_view(),name="join-request"),
    path('accept-join-request/<int:join_request_id>/', AcceptRideJoinRequestAPIView.as_view(), name='accept_join_request'),
    path('decline-join-request/<int:request_id>/',DeclineJoinRequestAPIView.as_view(),name='decline-request'),

]