from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rider_part.models import RideRequest
from . serializers import *
from rest_framework import status
from django.utils import timezone
from django.utils.timezone import localtime
import pytz
from . models import *
# Create your views here.


class ToggleOnlineStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({'status': 'error', 'message': 'Only drivers can toggle online status.'}, status=403)
        
        user.is_online = not user.is_online
        user.save()
        return Response({'status': 'success', 'is_online': user.is_online})
    
class DriverCashLimitAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({"error": "Only drivers have cash limit."}, status=403)

        return Response({"cash_payments_left": user.cash_payments_left})
    
class AvailableNowRidesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        city_name = request.data.get('city_name')

        if not city_name:
            return Response({"error": "City name is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response({"error": "City not found."}, status=status.HTTP_404_NOT_FOUND)

        rides = RideRequest.objects.filter(
            ride_type='now',
            status='pending',
            city=city
        )
        if not rides.exists():
            return Response({"message": "No rides available."}, status=status.HTTP_200_OK)

        serializer = RideNowDestinationSerializer(rides, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class AvailableScheduledRidesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        city_name = request.data.get('city_name')

        if not city_name:
            return Response({"error": "City name is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response({"error": "City not found."}, status=status.HTTP_404_NOT_FOUND)

        rides = RideRequest.objects.filter(
            ride_type='scheduled',
            status='pending',
            city=city
        ).exclude(
            declined_by_drivers__driver=request.user  # Exclude rides declined by this driver
            )
        if not rides.exists():
            return Response({"message": "No scheduled rides available."}, status=status.HTTP_200_OK)

        serializer = RideNowDestinationSerializer(rides, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class RideRequestDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.prefetch_related('ride_stops').get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideRequestDetailSerializer(ride)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeclineRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeclineRideSerializer(data=request.data)
        if serializer.is_valid():
            ride_id = serializer.validated_data['ride_id']
            driver = request.user
            ride = RideRequest.objects.get(id=ride_id)

            DeclinedRide.objects.get_or_create(ride=ride, driver=driver)

            return Response({"message": "Ride declined successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AcceptRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, status='pending')
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found or already accepted"}, status=status.HTTP_404_NOT_FOUND)

        ride.driver = request.user
        ride.status = 'accepted'
        ride.save()

        serializer = RideAcceptedDetailSerializer(ride)
        return Response({
            "message": "Ride accepted and driver assigned successfully.",
            "ride_details": serializer.data
        }, status=status.HTTP_200_OK)


class CancelRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found"}, status=status.HTTP_404_NOT_FOUND)

        if ride.driver != request.user:
            return Response({"error": "You are not allowed to cancel this ride."}, status=403)

        if ride.status in ['completed', 'cancelled']:
            return Response({"error": "Cannot cancel a completed or already cancelled ride."}, status=400)

        ride.status = 'cancelled'
        ride.save()

        return Response({"message": "Ride cancelled successfully."}, status=200)
    

class RideDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('user').prefetch_related('ride_stops').get(id=ride_id)
            serializer = RideDetailSerializer(ride)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except RideRequest.DoesNotExist:
            return Response({'error': 'Ride not found'}, status=status.HTTP_404_NOT_FOUND)
        

class RideDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({'detail': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RidePriceDetailSerializer(ride)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


# begin ride
class SetRideStartTimeAPIView(APIView):
    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        if ride.start_time:
            return Response({"detail": "Start time already set."}, status=status.HTTP_400_BAD_REQUEST)

        ist_time = ride.start_time.astimezone(pytz.timezone("Asia/Kolkata"))

        ride.start_time = timezone.now()
        ride.save()
        return Response({
            "ride_id": ride.id,
            "start_time": ride.start_time,
            "start_time_ist": ist_time.strftime('%Y-%m-%d %I:%M %p')
        }, status=status.HTTP_200_OK)
    


class SetRideEndTimeAPIView(APIView):
    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        if ride.end_time:
            return Response({"detail": "End time already set."}, status=status.HTTP_400_BAD_REQUEST)

        ride.end_time = timezone.now()
        ride.save()

        ist_time = ride.end_time.astimezone(pytz.timezone("Asia/Kolkata"))

        return Response({
            "ride_id": ride.id,
            "end_time_utc": ride.end_time,
            "end_time_ist": ist_time.strftime('%Y-%m-%d %I:%M %p')
        }, status=status.HTTP_200_OK)