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
            serializer.save(owner=request.user)
            return self.response(serializer.data, 201)  
        return self.response(serializer.errors, 400)  


class GetRideShareVehicleAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        vehicles = RideShareVehicle.objects.filter(owner=user)

        serializer = RideShareVehicleSerializer(vehicles, many=True, context={'request': request})
        return self.response(data=serializer.data, status_code=200)
    

class CreateRideAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_id):
        user = request.user

        try:
            vehicle = RideShareVehicle.objects.get(id=vehicle_id, owner=user)
        except RideShareVehicle.DoesNotExist:
            return self.response({
                "detail": "Vehicle not found or you do not own this vehicle."
            }, status_code=404)

        if not vehicle.approved:
            return self.response({
                "detail": "Vehicle is not approved by admin. Ride creation not allowed."
            }, status_code=400)

        serializer = RideCreateSerializer(
            data=request.data,
            context={'vehicle': vehicle, 'driver': user}
        )
        if serializer.is_valid():
            ride = serializer.save()
            return self.response(data={"ride_id": ride.id}, status_code=201)
        return self.response(serializer.errors, status_code=400)


class UpcomingRidesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        ist = pytz_timezone('Asia/Kolkata')
        now = datetime.now(ist)

        rides = Ride.objects.filter(driver=user).order_by('-ride_date', '-ride_time')

        if not rides.exists():
            return self.response(
                {"detail": "No upcoming rides found."},
                status_code=404
            )

        serializer = RideSerializer(rides, many=True, context={'request': request, 'current_time': now})
        return self.response(data=serializer.data, status_code=200)
    
class PublicRidesListAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        ist = pytz_timezone('Asia/Kolkata')
        now = datetime.now(ist)

        user = request.user if request.user.is_authenticated else None

        rides = Ride.objects.filter(vehicle__approved=True)

        if user:
            rides = rides.exclude(driver=user)
         
        upcoming_rides = []
        for ride in rides:
            ride_datetime = datetime.combine(ride.ride_date, ride.ride_time)
            ride_datetime = ist.localize(ride_datetime)
            if ride_datetime > now:
                upcoming_rides.append(ride)

        if not upcoming_rides:
            return self.response(
                {"detail": "No rides available at the moment."},
                status_code=404
            )

        serializer = PublicRideSerializer(upcoming_rides, many=True, context={'request': request})
        return self.response(data=serializer.data, status_code=200)
    
    
class JoinRideAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = Ride.objects.get(id=ride_id)
        except Ride.DoesNotExist:
            return self.response({"detail": "Ride not found."}, status_code=404)

        serializer = RideJoinRequestCreateSerializer(
            data=request.data,
            context={'request': request, 'ride': ride}
        )

        if serializer.is_valid():
            join_request = serializer.save()
            return self.response({
                "message": "Ride join request sent successfully.",
                "join_request_id": join_request.id
            }, status_code=201)

        return self.response(serializer.errors, status_code=400)
    

class RideJoinRequestsAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = Ride.objects.get(id=ride_id)
        except Ride.DoesNotExist:
            return self.response({"detail": "Ride not found."}, status_code=404)

        if ride.driver != request.user:
            return self.response({"detail": "You are not authorized to view join requests for this ride."}, status_code=403)

        join_requests = ride.join_requests.all().order_by('-requested_at')
        serializer = RideJoinRequestSerializer(join_requests, many=True, context={'request': request})
        return self.response(serializer.data)
    

class UserRequestedRidesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        requests = RideJoinRequest.objects.filter(user=user).select_related('ride__vehicle', 'ride__driver')

        if not requests.exists():
            return self.response({
                "message": "No ride join requests found.",
                "data": []
            })

        serializer = UserRequestedRideSerializer(requests, many=True, context={'request': request})
        return self.response(serializer.data)


class AcceptRideJoinRequestAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, join_request_id):
        try:
            join_request = RideJoinRequest.objects.select_related('ride', 'user').get(id=join_request_id)
        except RideJoinRequest.DoesNotExist:
            return self.response({"detail": "Join request not found."}, status_code=404)

        ride = join_request.ride

        # Check if the logged-in user is the driver of the ride
        if ride.driver != request.user:
            return self.response({"detail": "You are not authorized to accept this request."}, status_code=403)

        if join_request.status != 'pending':
            return self.response({"detail": f"Request is already {join_request.status}."}, status_code=400)

        if join_request.seats_requested > ride.seats_left:
            return self.response({"detail": "Not enough available seats to accept this request."}, status_code=400)

        # Accept the request
        join_request.status = 'accepted'
        join_request.save()

        # Reduce available seats in the ride
        ride.seats_left -= join_request.seats_requested
        ride.save()

        return self.response({
                "ride_id": ride.id,
                "seats_remaining": ride.seats_left
            }
        , status_code=200)
    

class DeclineJoinRequestAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        user = request.user

        join_request = get_object_or_404(RideJoinRequest, id=request_id)

        # Ensure only the ride owner (driver) can decline the request
        if join_request.ride.driver != user:
            return self.response({
                "detail": "You do not have permission to decline this request."
            }, status_code=403)

        if join_request.status != 'pending':
            return self.response({
                "detail": f"This request is already {join_request.status}."
            }, status_code=400)

        join_request.status = 'rejected'
        join_request.save()

        return self.response({
            "message": "Join request has been declined."
        }, status_code=200)