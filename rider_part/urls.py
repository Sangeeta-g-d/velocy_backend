from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
from . import serializers

urlpatterns = [
    path('vehicle-types/', VehicleTypeListView.as_view(), name='vehicle-type-list'),

    # ride request
    path('confirm_location/', RideRequestCreateView.as_view(), name='ride-request-create'),
    path('ride-stops/', AddRideStopAPIView.as_view(), name='add-ride-stop'),
    path('estimate-price/', EstimateRidePriceAPIView.as_view(), name='estimate-ride-price'),
    path('ride-booking/<int:ride_id>/', RideRequestUpdateAPIView.as_view(), name='ride-request-update'),

    # 12-6-25
   path('live-tracking/<int:ride_id>/', RideDetailsWithDriverView.as_view(), name='ride-details'),

]