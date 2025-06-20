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

    # 17-6-25 OTP validation between rider and driver
    path('generate-otp/<int:ride_id>/', GenerateRideOTPView.as_view()),
    path('verify-otp/<int:ride_id>/', VerifyRideOTPView.as_view()),

    # 18-6-25
    path('driver-payment-details/<int:ride_id>/', RideSummaryForDriverAPIView.as_view(), name='ride-summary-driver'),
    path('update-payment-status/', UpdateRidePaymentStatusAPIView.as_view(), name='update_ride_payment_status'),
    path('trip-completion/<int:ride_id>/', DriverRideEarningDetailAPIView.as_view(), name='driver-ride-earning-detail'),

    # 20-6-25
    path('driver-profile/',DriverNameAPIView.as_view(),name='driver-profile'),
    
]