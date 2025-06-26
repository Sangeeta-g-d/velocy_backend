from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from . models import *
# Create your views here.


class RegisterFCMDeviceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("fcm_token")
        device_type = request.data.get("device_type")
        device_id = request.data.get("device_id")  # New

        if not token or device_type not in ['android', 'ios']:
            return Response({"detail": "Invalid data"}, status=400)

        FCMDevice.objects.update_or_create(
            user=request.user,
            device_id=device_id,
            defaults={'token': token, 'device_type': device_type}
        )

        return Response({"message": "Device registered."})
