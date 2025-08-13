from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
from . import serializers

urlpatterns = [
    path('vehicle-types/', VehicleTypeListView.as_view(), name='vehicle-type-list'),
    path('rider-profile/', RiderProfileView.as_view(), name='rider_profile'),

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

    # 21-6-25
    path('rider-ride-history/',RiderPastRideHistoryAPIView.as_view(),name="ride-history"),
    path('upcoming-rides/', RiderScheduledRidesAPIView.as_view(), name='upcoming-rides'),

    # 23-6-25
    path('active-promos/', ActivePromoCodesAPIView.as_view(), name='active-promo-codes'),

    # corporate url
    path('corporate-home-screen/', EmployeeDashboardAPIView.as_view(), name='corporate_ride_request'),
    path('corporate-user-payment/<int:ride_id>/', RideCorporatePaymentSummaryAPIView.as_view(), name='ride_payment_summary'),
    path('corporate-confirm-payment/<int:ride_id>/', RideCorporateConfirmAPIView.as_view(), name='ride_confirm'),

    # reporting
    path('report-types/', RideReportListAPIView.as_view(), name='ride-reports'),
    path('submit-ride-report/', SubmitRideReportAPIView.as_view(), name='submit-ride-report'),

    # favorite locations
    path('add-favorite-to-location/', AddFavoriteToLocationAPIView.as_view(), name='add_favorite_to_location'),
    path('delete-favorites-to-location/<int:pk>/', DeleteFavoriteToLocationAPIView.as_view(), name='delete-favorite-to'),

    path('cancel-by-user/<int:ride_id>/', CancelRideByUserAPIView.as_view(), name='cancel-ride-by-user'),


    path('chat-history/<int:ride_id>/', RideChatHistoryAPIView.as_view(), name='ride-chat-history'),
    path('active-rides/',ActiveRideAPIView.as_view(),name="active-rides")
    
]