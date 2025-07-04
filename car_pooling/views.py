from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .serializers import *
from .mixins import StandardResponseMixin
from admin_part.models import City, CityVehiclePrice,VehicleType
from auth_api.models import DriverVehicleInfo

class EstimateRidePriceAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EstimatedPriceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        # Step 1: Get driver's vehicle info
        try:
            driver_vehicle = user.vehicle_info
        except DriverVehicleInfo.DoesNotExist:
            return Response({"detail": "Driver vehicle info not found."}, status=status.HTTP_400_BAD_REQUEST)

        # vehicle_type is a string like 'Sedan', get the VehicleType instance
        try:
            vehicle_type = VehicleType.objects.get(name__iexact=driver_vehicle.vehicle_type)
        except VehicleType.DoesNotExist:
            return Response({"detail": f"Vehicle type '{driver_vehicle.vehicle_type}' not found in VehicleType table."},
                            status=status.HTTP_404_NOT_FOUND)

        city_name = serializer.validated_data['city_name']
        distance_km = serializer.validated_data['distance_km']

        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response({"detail": f"City '{city_name}' not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            vehicle_price = CityVehiclePrice.objects.get(city=city, vehicle_type=vehicle_type)
        except CityVehiclePrice.DoesNotExist:
            return Response({"detail": f"No pricing found for {vehicle_type.name} in {city.name}."},
                            status=status.HTTP_404_NOT_FOUND)

        estimated_price = float(vehicle_price.price_per_km) * float(distance_km)

        return Response({
            "start_location": serializer.validated_data['start_location_name'],
            "end_location": serializer.validated_data['end_location_name'],
            "city": city.name,
            "vehicle_type": vehicle_type.name,
            "distance_km": distance_km,
            "price_per_km": vehicle_price.price_per_km,
            "estimated_price": round(estimated_price, 2)
        })
    
class CreateCarPoolRideAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CarPoolRideSerializer(data=request.data)
        if serializer.is_valid():
            ride = serializer.save(driver=request.user)
            return self.response({
                "ride_id": ride.id,
                "start_location": ride.start_location_name,
                "end_location": ride.end_location_name,
                "total_seats": ride.total_seats,
                "available_seats": ride.available_seats,
                "date": ride.date,
                "time": ride.time
            }, status_code=201)

        # 🔧 Extract first field and error message for better clarity
        try:
            field, error_list = next(iter(serializer.errors.items()))
            error_message = f"{field}: {error_list[0]}"
        except Exception:
            error_message = "Invalid input."

        return self.response({"detail": error_message}, status_code=400)
    

class AddRideStopAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = CarPoolRide.objects.get(id=ride_id, driver=request.user)
        except CarPoolRide.DoesNotExist:
            return self.response({"detail": "Ride not found or access denied."}, status_code=404)

        serializer = RideStopSerializer(data=request.data)
        if serializer.is_valid():
            max_order = RideStop.objects.filter(ride=ride).aggregate(max_order=models.Max('order'))['max_order'] or 0
            stop = serializer.save(ride=ride, order=max_order + 1)
            return self.response({
                "stop_id": stop.id,
                "ride_id": ride.id, 
                "location_name": stop.location_name,
                "order": stop.order
            }, status_code=201)

        # Skip 'ride' error and show first meaningful field error
        try:
            for field, errors in serializer.errors.items():
                if field != 'ride':
                    error_message = f"{field}: {errors[0]}"
                    break
            else:
                error_message = "Invalid input."
        except Exception:
            error_message = "Invalid input."

        return self.response({"detail": error_message}, status_code=400)