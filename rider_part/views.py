from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_part.models import VehicleType, CityVehiclePrice
from .serializers import *
from rest_framework import generics, permissions
from django.db.models import Avg
from decimal import Decimal
from auth_api.models import DriverRating
from . models import *
from rest_framework.permissions import IsAuthenticated
from admin_part.models import PromoCode, PromoCodeUsage
from django.db import IntegrityError
from django.core.exceptions import ValidationError

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


class RideDetailsWithDriverView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related(
                'driver', 'driver__vehicle_info'
            ).prefetch_related('ride_stops').get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideDetailSerializer(ride)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class DriverDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
            driver = ride.driver
            if not driver:
                return Response({"error": "Driver not assigned to this ride."}, status=400)

            vehicle_info = driver.vehicle_info  # From OneToOne relation
            avg_rating = DriverRating.objects.filter(driver=driver).aggregate(avg=Avg('rating'))['avg'] or 0.0

            data = {
                "driver": {
                    "username": driver.username,
                    "profile": driver.profile.url if driver.profile else None,
                    'phone_number':driver.phone_number
                },
                "avg_rating": round(avg_rating, 2),
                "vehicle_number": vehicle_info.vehicle_number,
                "vehicle_name": f"{vehicle_info.car_company} {vehicle_info.car_model}",
            }
            return Response(data)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=404)
        except DriverVehicleInfo.DoesNotExist:
            return Response({"error": "Driver vehicle info not found."}, status=404)
        

class RideRouteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.prefetch_related('ride_stops').get(id=ride_id)
            serializer = RideRouteSerializer(ride)
            return Response(serializer.data)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=404)
        

class RideSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
            serializer = RideSummaryFormattedSerializer(ride)
            return Response(serializer.data)
        except RideRequest.DoesNotExist:
            return Response({'error': 'Ride not found'}, status=404)
        
class ValidateAndApplyPromoCodeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        promo_code_str = request.data.get('promo_code')
        ride_id = request.data.get('ride_id')

        if not promo_code_str or not ride_id:
            return Response({"error": "Promo code and ride ID are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        ride_price = ride.offered_price or ride.estimated_price
        if ride_price is None:
            return Response({"error": "Price not available for this ride."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo = PromoCode.objects.get(code=promo_code_str)
        except PromoCode.DoesNotExist:
            return Response({"error": "Invalid promo code."}, status=status.HTTP_400_BAD_REQUEST)

        if not promo.is_valid(request.user, ride_price):
            return Response({"error": "Promo code is not valid or has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # Remove existing promo usage for this ride if any
        PromoCodeUsage.objects.filter(user=request.user, ride=ride).delete()

        # Calculate discount
        if promo.discount_type == 'flat':
            discount = promo.discount_value
        else:  # percent
            discount = (promo.discount_value / 100) * ride_price
            if promo.max_discount_amount:
                discount = min(discount, promo.max_discount_amount)

        final_price = max(ride_price - discount, 0)

        try:
            PromoCodeUsage.objects.create(
                user=request.user,
                promo_code=promo,
                ride=ride
            )
        except IntegrityError:
            return Response({"error": "Promo code already used for this ride."},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "success": True,
            "promo_code": promo.code,
            "original_price": float(ride_price),
            "discount": float(discount),
            "final_price": float(final_price),
            "message": "Promo code applied successfully."
        }, status=status.HTTP_200_OK)
    
class FinalizeRidePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ride_id = request.data.get('ride_id')
        payment_method = request.data.get('payment_method')
        tip_amount = request.data.get('tip_amount', 0)

        # Validate required fields
        if not ride_id or not payment_method:
            return Response({"error": "Ride ID and payment method are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        # ✅ Validate payment method
        valid_payment_methods = dict(RidePaymentDetail.PAYMENT_METHOD_CHOICES).keys()
        if payment_method not in valid_payment_methods:
            return Response({"error": f"Invalid payment method. Must be one of {list(valid_payment_methods)}."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Fetch the ride
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        # Prevent duplicate payments
        if RidePaymentDetail.objects.filter(ride=ride).exclude(payment_status='pending').exists():
            return Response({"error": "Payment details already submitted for this ride."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Safe tip conversion
        try:
            tip_amount = Decimal(tip_amount)
        except:
            return Response({"error": "Invalid tip amount."}, status=status.HTTP_400_BAD_REQUEST)

        ride_price = ride.offered_price or ride.estimated_price
        if ride_price is None:
            return Response({"error": "Price not available for this ride."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Promo code logic
        try:
            promo_usage = PromoCodeUsage.objects.get(user=request.user, ride=ride)
            promo = promo_usage.promo_code
            if promo.discount_type == 'flat':
                discount = promo.discount_value
            else:
                discount = (promo.discount_value / 100) * ride_price
                if promo.max_discount_amount:
                    discount = min(discount, promo.max_discount_amount)
        except PromoCodeUsage.DoesNotExist:
            promo = None
            discount = Decimal(0)

        grand_total = max(ride_price - discount, 0) + tip_amount
        driver_earning = ride_price  # Promo/tip doesn't affect driver earning

        payment_detail, created = RidePaymentDetail.objects.update_or_create(
            ride=ride,
            defaults={
                'user': request.user,
                'promo_code': promo,
                'promo_discount': discount,
                'tip_amount': tip_amount,
                'grand_total': grand_total,
                'payment_method': payment_method,
                'payment_status': 'pending',
                'driver_earnings': driver_earning,
            }
        )

        return Response({
            "success": True,
            "ride_id": ride.id,
            "promo_code": promo.code if promo else None,
            "promo_discount": float(discount),
            "tip_amount": float(tip_amount),
            "grand_total": float(grand_total),
            "payment_method": payment_method,
            "message": "Payment details recorded successfully."
        }, status=status.HTTP_200_OK)


class RiderRideDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('driver', 'payment_detail').get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get driver details
        driver = ride.driver
        driver_info = None
        avg_rating = None

        if driver:
            avg_rating = DriverRating.objects.filter(driver=driver).aggregate(avg=Avg('rating'))['avg']
            driver_info = {
                "id": driver.id,
                "username": driver.username,
                "profile_image": (
                    driver.profile.url if hasattr(driver, 'profile') and driver.profile else None
                ),
                "average_rating": round(float(avg_rating), 1) if avg_rating else None,
            }

        # Get payment details
        ride_price = float(ride.offered_price or ride.estimated_price or 0)
        payment = getattr(ride, 'payment_detail', None)
        if payment:
            payment_summary = {
                "ride_price": ride_price,
                "payment_method": payment.payment_method,
                "promo_code": payment.promo_code.code if payment.promo_code else None,
                "promo_discount": float(payment.promo_discount),
                "tip_amount": float(payment.tip_amount),
                "total_paid": float(payment.grand_total),
            }
        else:
            payment_summary = {
                "payment_method": None,
                "promo_code": None,
                "promo_discount": 0.0,
                "tip_amount": 0.0,
                "total_paid": float(ride.offered_price or ride.estimated_price or 0)
            }

        return Response({
            "ride_id": ride.id,
            "from_location": ride.from_location,
            "to_location": ride.to_location,
            "distance_km": float(ride.distance_km),
            "start_time": ride.start_time,
            "end_time": ride.end_time,
            "driver": driver_info,
            "payment_summary": payment_summary
        }, status=status.HTTP_200_OK)
    


class RateDriverAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        rating = request.data.get('rating')
        review = request.data.get('review', '')

        # ✅ Validate rating presence
        if not rating:
            return Response({"error": "Rating is required."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Validate ride
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user, status='completed')
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found or not completed."}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Check if already rated
        if hasattr(ride, 'driver_rating'):
            return Response({"error": "You have already rated this ride."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rating_value = Decimal(rating)
            if rating_value < 1 or rating_value > 5:
                raise ValidationError("Rating must be between 1 and 5.")
        except:
            return Response({"error": "Invalid rating value."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create rating
        DriverRating.objects.create(
            ride=ride,
            driver=ride.driver,
            rated_by=request.user,
            rating=rating_value,
            review=review
        )

        return Response({"message": "Rating submitted successfully."}, status=status.HTTP_201_CREATED)