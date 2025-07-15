from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from .mixins import StandardResponseMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from datetime import datetime, time
from . models import *
from pytz import timezone as pytz_timezone
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from datetime import date


class AddRideShareVehicleAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RideShareVehicleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return self.response(serializer.data, 201)
        return self.response(serializer.errors, 400)
 

class GetRideShareVehicleAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        vehicles = RideShareVehicle.objects.filter(owner=user)

        serializer = RideShareVehicleSerializer(vehicles, many=True, context={'request': request})
        return self.response(data=serializer.data, status_code=200)
    
class CreateRideShareBookingAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_id):
        try:
            vehicle = RideShareVehicle.objects.get(id=vehicle_id)
        except RideShareVehicle.DoesNotExist:
            return self.response({"error": "Vehicle not found."}, status_code=404)

        if not vehicle.approved:
            return self.response({"error": "Vehicle is not approved yet."}, status_code=400)

        data = request.data.copy()
        data['vehicle'] = vehicle.id  # Inject vehicle ID into serializer data

        serializer = RideShareBookingCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            booking = serializer.save()
            return self.response({
                'booking_id': booking.id,
                'status': booking.status,
                'message': 'Ride booking created in draft status.'
            }, status_code=201)

        return self.response(serializer.errors, status_code=400)