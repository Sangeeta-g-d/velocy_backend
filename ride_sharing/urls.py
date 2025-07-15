from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
from . import serializers

urlpatterns = [
    path('add-vehicle/', AddRideShareVehicleAPIView.as_view(), name='add_ride_share_vehicle'),
    path('my-vehicles/', GetRideShareVehicleAPIView.as_view(), name='get_my_vehicles'),
    path('create-trip/<int:vehicle_id>/', CreateRideShareBookingAPIView.as_view(), name='create_rideshare_booking'),
]