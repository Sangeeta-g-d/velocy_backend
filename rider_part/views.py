from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_part.models import VehicleType, CityVehiclePrice
from .serializers import *
from rest_framework import generics, permissions
from . models import *
from rest_framework.permissions import IsAuthenticated

class VehicleTypeListView(APIView):
    def get(self, request):
        vehicle_types = VehicleType.objects.all()
        serializer = VehicleTypeSerializer(vehicle_types, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class RideRequestCreateView(generics.CreateAPIView):
    queryset = RideRequest.objects.all()
    serializer_class = RideRequestCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


class AddRideStopAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RideStopSerializer(data=request.data)
        if serializer.is_valid():
            ride = serializer.validated_data['ride']
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']

            # Check for duplicate stop in the same ride
            if RideStop.objects.filter(ride=ride, latitude=latitude, longitude=longitude).exists():
                return Response(
                    {"error": "This stop already exists for the selected ride."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Assign next order
            existing_stops_count = RideStop.objects.filter(ride=ride).count()
            serializer.save(order=existing_stops_count + 1)

            return Response({
                "message": "Stop added successfully",
                "stop": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EstimateRidePriceAPIView(APIView):
    def post(self, request):
        serializer = EstimatePriceInputSerializer(data=request.data)
        if serializer.is_valid():
            ride_id = serializer.validated_data['ride_id']
            vehicle_type_id = serializer.validated_data['vehicle_type_id']

            try:
                ride = RideRequest.objects.get(id=ride_id)
            except RideRequest.DoesNotExist:
                return Response({"error": "Ride not found"}, status=status.HTTP_404_NOT_FOUND)

            if not ride.city:
                return Response({"error": "City not selected for this ride."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                price_entry = CityVehiclePrice.objects.get(city=ride.city, vehicle_type_id=vehicle_type_id)
            except CityVehiclePrice.DoesNotExist:
                return Response({"error": "Pricing not found for this city and vehicle type."}, status=status.HTTP_404_NOT_FOUND)

            # Calculate estimated price
            estimated_price = price_entry.price_per_km * ride.distance_km

            # Save estimated price and vehicle type in the RideRequest model
            ride.estimated_price = round(estimated_price, 2)
            ride.vehicle_type_id = vehicle_type_id
            ride.save()

            return Response({
                "message": "Estimated price updated in the ride.",
                "vehicle_type_id": vehicle_type_id,
                "price_per_km": price_entry.price_per_km,
                "distance_km": ride.distance_km,
                "estimated_price": round(estimated_price, 2)
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    

class RideRequestUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideRequestUpdateSerializer(ride, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Ride request updated successfully",
                "ride": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
