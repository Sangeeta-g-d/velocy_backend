from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
from . import serializers

urlpatterns = [
    path('add-vehicle/', AddRideShareVehicleAPIView.as_view(), name='add_ride_share_vehicle'),
    path('my-vehicles/', GetRideShareVehicleAPIView.as_view(), name='get_my_vehicles'),
    path('create-trip/', CreateRideShareCompleteAPIView.as_view(), name='create_rideshare_booking'),
    # path('add-stop/<int:booking_id>/', AddRideShareStopAPIView.as_view(), name='add_rideshare_stop'),
    path('estimate-price-range/<int:booking_id>/', EstimateBookingPriceAPIView.as_view(), name='estimate_booking_price'),
    path('ride-segments-price/<int:ride_id>/', RideSegmentListAPIView.as_view(), name='ride_segments'),
    path('update-segment-prices/<int:ride_id>/', BulkUpdateRideSegmentPricesAPIView.as_view(), name='update_ride_segment_prices'),
    path('add-ride-return-details/<int:ride_id>/', UpdateReturnRideDetailsAPIView.as_view(), name='update_return_ride'),
    path('update-ride-price/<int:ride_id>/', RidePriceUpdateAPIView.as_view(), name='update_ride_price'),
    path('my-published-rides/', UserPublishedRidesAPIView.as_view(), name='my_published_rides'),
    path('ride-details/<int:ride_id>/', RideStopSegmentListAPIView.as_view(), name='ride_details'),
    path("search/", RideShareSearchAPIView.as_view(), name="ride_share_search"),
    path('ride-join-request/', RideJoinRequestAPIView.as_view(), name='ride-join-request'),
    path('view-join-requests/<int:ride_id>/', RideJoinRequestsByRideView.as_view(), name='ride-join-requests'),
    path('accept-ride-join-request/<int:ride_request_id>/', AcceptRideJoinRequestAPIView.as_view(), name='accept-ride-join-request'),
    path('cancel-join-request/<int:join_request_id>/', CancelJoinRequestAPIView.as_view(), name='cancel-join-request'),
    path('my-ride-join-requests/', MyRideJoinRequestsAPIView.as_view(), name='my_ride_join_requests'),
    path('accepted-join-requests/<int:ride_id>/', AcceptedJoinRequestsAPIView.as_view(), name='accepted-join-requests'),
    path('cancel-ride/<int:ride_id>/', CancelRideAPIView.as_view(), name='cancel-ride'),
    path('sharing-ride-details/', RideDetailsAPIView.as_view(), name='ride_share_booking_detail'),
    path('sharing-ride-start/<int:ride_id>/', RideStartAPIView.as_view(), name='ride-share-start'),
    path('sharing-ride-end/<int:ride_id>/', RideEndAPIView.as_view(), name='ride-share-end'),
    path('payment-summary/<int:join_request_id>/', RidePaymentSummaryAPIView.as_view(), name='ride-payment-summary'),
    path('driver-payment-summary/<int:join_request_id>/', DriverRidePaymentAPIView.as_view(), name='shared-ride-payment-summary'),
    path('complete-shared-ride/<int:ride_id>/', CompleteRideShareBookingAPIView.as_view(), name='complete-ride-share'),
    path('rate-ride/<int:ride_join_request_id>/', RateRideAPIView.as_view(), name='rate-ride'),
]