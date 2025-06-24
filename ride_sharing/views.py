from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from .mixins import StandardResponseMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from . models import *
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

        serializer = RideCreateSerializer(data=request.data)
        if serializer.is_valid():
            ride = serializer.save(vehicle=vehicle, driver=user)
            return self.response(data={"ride_id": ride.id}, status_code=201)
        return self.response(serializer.errors, status_code=400)
    

class UpcomingRidesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = date.today()

        rides = Ride.objects.filter(driver=user, ride_date__gte=today).order_by('ride_date', 'ride_time')

        if not rides.exists():
            return self.response(
                {"detail": "No upcoming rides found."},
                status_code=404
            )

        serializer = RideSerializer(rides, many=True, context={'request': request})
        return self.response(data=serializer.data, status_code=200)
    
class PublicRidesListAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        today = date.today()
        user = request.user if request.user.is_authenticated else None

        rides = Ride.objects.filter(
            ride_date__gte=today,
            vehicle__approved=True
        ).select_related('driver')

        if user:
            rides = rides.exclude(driver=user)

        rides = rides.order_by('ride_date', 'ride_time')

        if not rides.exists():
            return self.response(
                {"detail": "No rides available at the moment."},
                status_code=404
            )

        serializer = PublicRideSerializer(rides, many=True, context={'request': request})
        return self.response(data=serializer.data)
    
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