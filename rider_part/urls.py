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

    # 17-6-25
    path('driver-arrived-screen/<int:ride_id>/', DriverDetailsAPIView.as_view(), name='driver-details'),
    path('route-with-driver/<int:ride_id>/', RideRouteAPIView.as_view(), name='ride-route'),
    path('ride-complete/<int:ride_id>/', RideSummaryAPIView.as_view(), name='ride-summary'),
    path('validate-promo/', ValidateAndApplyPromoCodeAPIView.as_view(), name='validate-promo'),

    # 18-6-25
    path('finalize-payment/', FinalizeRidePaymentAPIView.as_view(), name='finalize_ride_payment'),
    path('rider-trip-completion/<int:ride_id>/',RiderRideDetailAPIView.as_view(),name='rider_trip_completion'),
    path('rate-driver/<int:ride_id>/', RateDriverAPIView.as_view(), name='rate_driver'),
    
]