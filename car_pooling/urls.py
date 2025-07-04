from django.urls import path
from .views import *
from . import serializers

urlpatterns = [
    path('estimated-price/', EstimateRidePriceAPIView.as_view(), name='create-carpool-ride'),
    path('create-ride/', CreateCarPoolRideAPIView.as_view(), name='create-car-pool-ride'),
    path('add-stop/<int:ride_id>/',AddRideStopAPIView.as_view(),name="add-stops")
]