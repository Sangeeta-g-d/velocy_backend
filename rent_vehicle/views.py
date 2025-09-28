from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from . models import *
import json
from .serializers import *
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets, permissions, status

class RentedVehicleCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = RentedVehicleCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Vehicle listed successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRentedVehicleListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        vehicles = RentedVehicle.objects.filter(user=user).order_by('-id')

        if not vehicles.exists():
            return Response(
                {"message": "No vehicles found for this user."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = UserRentedVehicleListSerializer(vehicles, many=True,context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class DeleteRentedVehicleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, vehicle_id):
        try:
            vehicle = RentedVehicle.objects.get(id=vehicle_id, user=request.user)
        except RentedVehicle.DoesNotExist:
            return Response({"error": "Vehicle not found or you do not have permission to delete it."},
                            status=status.HTTP_404_NOT_FOUND)
        vehicle.delete()
        return Response({"message": "Vehicle deleted successfully."}, status=status.HTTP_200_OK)
    

# edit
# fetch
class RentedVehicleDetailForEditAPIView(APIView):
  
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, vehicle_id):
        rented_vehicle = get_object_or_404(RentedVehicle, id=vehicle_id)
        serializer = RentedVehicleUpdateSerializer(rented_vehicle)
        return Response(serializer.data)
    
class RentedVehicleUpdateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        vehicle = get_object_or_404(RentedVehicle, pk=pk, user=request.user)
        serializer = RentedVehicleUpdateSerializer(vehicle, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            # ✅ Handle image updates
            image_updates = request.data.getlist('update_images')  # JSON strings
            for image_json in image_updates:
                try:
                    image_dict = json.loads(image_json)
                    image_id = image_dict.get('id')
                    image_file = request.FILES.get(str(image_id))
                    if image_id and image_file:
                        img_obj = RentedVehicleImage.objects.get(id=image_id, vehicle=vehicle)
                        img_obj.image = image_file
                        img_obj.save()
                except Exception as e:
                    continue  # optionally log

            # ✅ Handle new images
            new_images = request.FILES.getlist('new_images')
            for image_file in new_images:
                RentedVehicleImage.objects.create(vehicle=vehicle, image=image_file)

            return Response({
                "message": "Vehicle updated successfully (including images)",
                "vehicle": RentedVehicleUpdateSerializer(vehicle).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# rented vehicle home screen 
class ApprovedVehiclesListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vehicle_type = request.query_params.get('vehicle_type')  # Get vehicle type from query params

        # Base queryset
        vehicles = RentedVehicle.objects.filter(is_approved=True)

        # Apply filter if vehicle_type is provided and valid
        if vehicle_type in dict(RentedVehicle.VEHICLE_TYPE_CHOICES).keys():
            vehicles = vehicles.filter(vehicle_type=vehicle_type)

        serializer = RentedVehicleHomeScreenListSerializer(vehicles, many=True, context={'request': request})

        return Response(serializer.data, status=status.HTTP_200_OK)
    

    
# vehicle details
class RentedVehicleDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, vehicle_id):
        try:
            vehicle = RentedVehicle.objects.select_related('user').get(id=vehicle_id)
        except RentedVehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RentedVehicleDetailSerializer(vehicle)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# vehicle owner details
class RentedVehicleOwnerInfoAPIView(APIView):
    def get(self, request, vehicle_id):
        try:
            vehicle = RentedVehicle.objects.select_related('user').get(id=vehicle_id)
        except RentedVehicle.DoesNotExist:
            return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RentedVehicleOwnerDetailSerializer(vehicle)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# rental request
class CreateRentalRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, vehicle_id):
        try:
            vehicle = RentedVehicle.objects.get(id=vehicle_id, is_available=True, is_approved=True)
        except RentedVehicle.DoesNotExist:
            return Response({"error": "Vehicle not available or not approved."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RentalRequestCreateSerializer(
            data=request.data,
            context={'request': request, 'vehicle': vehicle}
        )

        if serializer.is_valid():
            rental_request = serializer.save()
            return Response({
                "message": "Rental request created successfully.",
                "data": {
                    "id": rental_request.id,
                    "pickup": rental_request.pickup_datetime,
                    "dropoff": rental_request.dropoff_datetime,
                    "duration_hours": rental_request.duration_hours,
                    "total_price": float(rental_request.total_rent_price),
                    "status": rental_request.status
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class SentRentalRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rental_requests = RentalRequest.objects.filter(user=request.user).order_by('-requested_at')
        serializer = RentalRequestListSerializer(rental_requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

# lessor rental request list
class LessorRentalRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rental_requests = RentalRequest.objects.filter(lessor=request.user).select_related('user', 'vehicle')
        serializer = LessorRentalRequestSerializer(rental_requests, many=True)
        return Response(serializer.data)
    

class RentalRequestDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, rent_id):
        try:
            rental_request = RentalRequest.objects.get(id=rent_id)
        except RentalRequest.DoesNotExist:
            return Response({"error": "Rental request not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RentalRequestDetailSerializer(rental_request, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# accept rental request
class AcceptRentalRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, rent_id):
        try:
            rental_request = RentalRequest.objects.get(id=rent_id)
        except RentalRequest.DoesNotExist:
            return Response({"error": "Rental request not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure only the lessor can confirm the request
        if rental_request.lessor != request.user:
            return Response({"error": "You are not authorized to confirm this rental request."},
                            status=status.HTTP_403_FORBIDDEN)

        if rental_request.status != 'pending':
            return Response({"error": f"This request is already {rental_request.status}."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Update status to confirmed
        rental_request.status = 'confirmed'
        rental_request.save()

        return Response({"message": "Rental request confirmed successfully."}, status=status.HTTP_200_OK)
    

class RejectRentalRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, rent_id):
        try:
            rental_request = RentalRequest.objects.get(id=rent_id)
        except RentalRequest.DoesNotExist:
            return Response({"error": "Rental request not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure only the lessor can confirm the request
        if rental_request.lessor != request.user:
            return Response({"error": "You are not authorized to reject this rental request."},
                            status=status.HTTP_403_FORBIDDEN)

        if rental_request.status != 'pending':
            return Response({"error": f"This request is already {rental_request.status}."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Update status to confirmed
        rental_request.status = 'rejected'
        rental_request.save()

        return Response({"message": "Rental request rejected successfully."}, status=status.HTTP_200_OK)
    

class RentalRequestVehicleInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, rent_request_id):
        try:
            rental_request = RentalRequest.objects.get(id=rent_request_id, lessor=request.user)
        except RentalRequest.DoesNotExist:
            return Response({"error": "Rental request not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RentalRequestVehicleInfoSerializer(rental_request, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

# handover checklist
class HandoverChecklistAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, rental_request_id):
        try:
            rental_request = RentalRequest.objects.get(id=rental_request_id)
        except RentalRequest.DoesNotExist:
            return Response({"error": "Rental request not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if checklist already exists (update if exists)
        try:
            checklist = rental_request.handover_checklist
            serializer = HandoverChecklistSerializer(checklist, data=request.data, partial=True)
        except HandoverChecklist.DoesNotExist:
            serializer = HandoverChecklistSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(rental_request=rental_request)
            return Response({"message": "Checklist saved successfully.", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class RentalHandoverDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, rental_request_id):
        try:
            rental_request = RentalRequest.objects.get(id=rental_request_id, user=request.user)
        except RentalRequest.DoesNotExist:
            return Response({"error": "Rental request not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RentalHandoverDetailSerializer(rental_request)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ToggleVehicleAvailabilityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        vehicle = get_object_or_404(RentedVehicle, pk=pk, user=request.user)

        # Toggle availability
        vehicle.is_available = not vehicle.is_available
        vehicle.save()

        return Response({
            "message": f"Vehicle availability toggled to {'available' if vehicle.is_available else 'unavailable'}",
            "is_available": vehicle.is_available
        }, status=status.HTTP_200_OK)
    
class CancelRentalRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, rental_request_id):
        try:
            rental_request = RentalRequest.objects.get(id=rental_request_id, user=request.user)
        except RentalRequest.DoesNotExist:
            return Response({"detail": "Rental request not found."},
                            status=status.HTTP_404_NOT_FOUND)

        if rental_request.status in ['cancelled', 'completed', 'rejected']:
            return Response({"detail": "This request cannot be cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Free or paid cancellation check (optional)
        if rental_request.can_cancel_for_free():
            cancel_note = "Request cancelled successfully (free cancellation)."
        else:
            cancel_note = "Request cancelled successfully (cancellation fee may apply)."

        rental_request.status = 'cancelled'
        rental_request.cancelled_at = timezone.now()
        rental_request.save()

        return Response({"detail": cancel_note},
                        status=status.HTTP_200_OK)