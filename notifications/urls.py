from django.urls import path
from .views import RegisterFCMDeviceAPIView
from . import serializers

urlpatterns = [
    path('register-device/', RegisterFCMDeviceAPIView.as_view(), name='register-fcm-device'),

]