from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
from . import serializers

urlpatterns = [
    path('add-vehicle/', AddRideShareVehicleAPIView.as_view(), name='add_ride_share_vehicle'),
    path('my-vehicles/', GetRideShareVehicleAPIView.as_view(), name='get_my_vehicles'),
    path('create-trip/<int:vehicle_id>/', CreateRideShareBookingAPIView.as_view(), name='create_rideshare_booking'),
    path('add-stop/<int:booking_id>/', AddRideShareStopAPIView.as_view(), name='add_rideshare_stop'),
    path('estimate-price-range/<int:booking_id>/', EstimateBookingPriceAPIView.as_view(), name='estimate_booking_price'),
    path('ride-segments-price/<int:ride_id>/', RideSegmentListAPIView.as_view(), name='ride_segments'),
    path('update-segment-prices/<int:ride_id>/', BulkUpdateRideSegmentPricesAPIView.as_view(), name='update_ride_segment_prices'),
    path('add-ride-return-details/<int:ride_id>/', UpdateReturnRideDetailsAPIView.as_view(), name='update_return_ride'),
    path('update-ride-price/<int:ride_id>/', RidePriceUpdateAPIView.as_view(), name='update_ride_price'),
    path('my-published-rides/', UserPublishedRidesAPIView.as_view(), name='my_published_rides'),
    path('ride-details/<int:ride_id>/', RideStopSegmentListAPIView.as_view(), name='ride_details'),
]