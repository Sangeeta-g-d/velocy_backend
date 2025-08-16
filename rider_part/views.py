from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from admin_part.models import VehicleType, CityVehiclePrice
from .serializers import *
from rest_framework import generics, permissions
from django.db.models import Avg
from decimal import Decimal, InvalidOperation
from decimal import Decimal
from auth_api.models import DriverRating
from django.db.models import Q
from django.shortcuts import get_object_or_404
from corporate_web.models import CompanyPrepaidPlan
from django.db import transaction
from corporate_web.models import EmployeeCredit
from . models import *
from rest_framework.permissions import IsAuthenticated
from .mixins import StandardResponseMixin
from admin_part.models import PromoCode, PromoCodeUsage
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from admin_part.models import PlatformSetting


class VehicleTypeListView(StandardResponseMixin,APIView):
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


class AddRideStopAPIView(StandardResponseMixin,APIView):
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
                    {"detail": "This stop already exists for the selected ride."},
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

class EstimateRidePriceAPIView(StandardResponseMixin, APIView):
    def post(self, request):
        serializer = EstimatePriceInputSerializer(data=request.data)
        if serializer.is_valid():
            ride_id = serializer.validated_data['ride_id']
            vehicle_type_id = serializer.validated_data['vehicle_type_id']

            # Fetch ride
            try:
                ride = RideRequest.objects.get(id=ride_id)
            except RideRequest.DoesNotExist:
                return Response({"detail": "Ride not found"}, status=status.HTTP_404_NOT_FOUND)

            # Ride must be draft or pending
            if ride.status not in ['draft', 'pending']:
                return Response(
                    {"detail": "Estimated price can only be updated for draft or pending rides."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # City must be assigned
            if not ride.city:
                return Response({"detail": "City not selected for this ride."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch city pricing
            try:
                price_entry = CityVehiclePrice.objects.get(city=ride.city, vehicle_type_id=vehicle_type_id)
            except CityVehiclePrice.DoesNotExist:
                return Response(
                    {"detail": "Pricing not found for this city and vehicle type."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Calculate price
            estimated_price = price_entry.price_per_km * ride.distance_km
            rounded_price = round(estimated_price, 2)

            # 🔐 Check employee credit if ride is official
            if ride.ride_purpose == 'official' and request.user.role == 'employee':
                try:
                    employee_credit = request.user.credit
                except EmployeeCredit.DoesNotExist:
                    return Response(
                        {"detail": "Employee credits not found."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if not employee_credit.is_active:
                    return Response(
                        {"detail": "Your employee credits are inactive."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if employee_credit.available_credits() < rounded_price:
                    return Response(
                        {
                            "detail": "Insufficient credit balance for this ride.",
                            "available_credits": float(employee_credit.available_credits()),
                            "estimated_price": float(rounded_price),
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Save estimate to ride
            ride.estimated_price = rounded_price
            ride.vehicle_type_id = vehicle_type_id
            ride.save()

            return Response({
                "message": "Estimated price updated in the ride.",
                "vehicle_type_id": vehicle_type_id,
                "price_per_km": price_entry.price_per_km,
                "distance_km": ride.distance_km,
                "estimated_price": rounded_price,
                "user_role": request.user.role
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    

class RideRequestUpdateAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideRequestUpdateSerializer(ride, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Ride request updated successfully",
                "ride": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RideDetailsWithDriverView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related(
                'driver', 'driver__vehicle_info'
            ).prefetch_related('ride_stops').get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideDetailSerializer(ride,context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class DriverDetailsAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id,status="accepted")
            driver = ride.driver
            if not driver:
                return Response({"detail": "Driver not assigned to this ride."}, status=400)

            vehicle_info = driver.vehicle_info  # From OneToOne relation
            avg_rating = DriverRating.objects.filter(driver=driver).aggregate(avg=Avg('rating'))['avg'] or 0.0

            return Response(
                {
                "driver": {
                    "username": driver.username,
                    "profile": request.build_absolute_uri(driver.profile.url) if driver.profile else None,
                    'phone_number':driver.phone_number
                },
                "avg_rating": round(avg_rating, 2),
                "vehicle_number": vehicle_info.vehicle_number,
                "vehicle_name": f"{vehicle_info.car_company} {vehicle_info.car_model}"}
            )
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=404)
        except DriverVehicleInfo.DoesNotExist:
            return Response({"detail": "Driver vehicle info not found."}, status=404)
        

class RideRouteAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.prefetch_related('ride_stops').get(id=ride_id,status="accepted")
            serializer = RideRouteSerializer(ride)
            return Response(serializer.data)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=404)
        

class RideSummaryAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user,status="accepted")
            serializer = RideSummaryFormattedSerializer(ride)
            return Response(serializer.data)
        except RideRequest.DoesNotExist:
            return Response({'detial': 'Ride not found'}, status=404)
        
class ValidateAndApplyPromoCodeAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        promo_code_str = request.data.get('promo_code')
        ride_id = request.data.get('ride_id')

        if not promo_code_str or not ride_id:
            return Response({"detail": "Promo code and ride ID are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        # ❌ Prevent promo application if it's an official ride
        if ride.ride_purpose == 'official':
            return Response({"detail": "Promo codes cannot be applied to official rides."},
                            status=status.HTTP_400_BAD_REQUEST)

        ride_price = ride.offered_price or ride.estimated_price
        if ride_price is None:
            return Response({"detail": "Price not available for this ride."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo = PromoCode.objects.get(code=promo_code_str)
        except PromoCode.DoesNotExist:
            return Response({"detail": "Invalid promo code."}, status=status.HTTP_400_BAD_REQUEST)

        if not promo.is_valid(request.user, ride_price):
            return Response({"detail": "Promo code is not valid or has expired."}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response({"detail": "Promo code already used for this ride."},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "promo_code": promo.code,
            "original_price": float(ride_price),
            "discount": float(discount),
            "final_price": float(final_price),
            "message": "Promo code applied successfully."
        }, status=status.HTTP_200_OK)
    


class FinalizeRidePaymentAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ride_id = request.data.get('ride_id')
        payment_method = request.data.get('payment_method')
        upi_payment_id = request.data.get('upi_payment_id')

        # ------------------------------------------------------------------
        # 1) TIP AMOUNT (safe conversion)
        # ------------------------------------------------------------------
        tip_amount_raw = request.data.get('tip_amount', 0)

        try:
            if tip_amount_raw in [None, '', 'null']:
                tip_amount = Decimal(0)
            else:
                tip_amount = Decimal(str(tip_amount_raw).strip())
        except (InvalidOperation, ValueError):
            return Response(
                {"detail": "Invalid tip amount."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------------------------------------
        # 2) RIDE & PAYMENT VALIDATION
        # ------------------------------------------------------------------
        if not ride_id or not payment_method:
            return Response({"detail": "Ride ID and payment method are required."}, status=status.HTTP_400_BAD_REQUEST)

        valid_payment_methods = dict(RidePaymentDetail.PAYMENT_METHOD_CHOICES).keys()
        if payment_method not in valid_payment_methods:
            return Response({"detail": f"Invalid payment method. Must be one of {list(valid_payment_methods)}."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        if RidePaymentDetail.objects.filter(ride=ride).exclude(payment_status='pending').exists():
            return Response({"detail": "Payment already submitted."}, status=status.HTTP_400_BAD_REQUEST)

        # ------------------------------------------------------------------
        # 3) PRICE CALCULATION
        # ------------------------------------------------------------------
        ride_price = ride.offered_price or ride.estimated_price
        if ride_price is None:
            return Response({"detail": "Price not available."}, status=status.HTTP_400_BAD_REQUEST)

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
        driver_earning = ride_price

        # ------------------------------------------------------------------
        # 4) HANDLE PAYMENT + WEBSOCKET
        # ------------------------------------------------------------------
        payment_status = 'pending'
        if payment_method == 'upi':
            if not upi_payment_id:
                return Response({"detail": "UPI Payment ID is required for UPI method."}, status=status.HTTP_400_BAD_REQUEST)

            payment_status = 'completed'
            ride.status = 'completed'

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'payment_normal_ride_{ride.id}',
                {
                    'type': 'payment_status_update',
                    'payment_status': 'completed',
                    'message': f'UPI payment successful. Ride #{ride.id} marked as completed.',
                }
            )
            ride.save()

            # Add wallet credit for driver
            platform_fee = Decimal('0')
            active_fee = PlatformSetting.objects.filter(is_active=True).first()
            if active_fee:
                if active_fee.fee_type == 'percentage':
                    platform_fee = (active_fee.fee_value / 100) * driver_earning
                else:
                    platform_fee = active_fee.fee_value

            net_earning = driver_earning - platform_fee + tip_amount
            DriverWalletTransaction.objects.create(
                driver=ride.driver,
                ride=ride,
                amount=net_earning,
                transaction_type='ride_earning',
                description=f"Auto-completed UPI payment for Ride #{ride.id}"
            )

        # ------------------------------------------------------------------
        # 5) SAVE PAYMENT RECORD
        # ------------------------------------------------------------------
        RidePaymentDetail.objects.update_or_create(
            ride=ride,
            defaults={
                'user': request.user,
                'promo_code': promo,
                'promo_discount': discount,
                'tip_amount': tip_amount,
                'grand_total': grand_total,
                'payment_method': payment_method,
                'payment_status': payment_status,
                'driver_earnings': driver_earning,
                'upi_payment_id': upi_payment_id if payment_method == 'upi' else None,
            }
        )

        return Response({
            "ride_id": ride.id,
            "promo_code": promo.code if promo else None,
            "promo_discount": float(discount),
            "tip_amount": float(tip_amount),
            "grand_total": float(grand_total),
            "payment_method": payment_method,
            "payment_status": payment_status,
            "message": "Payment successful and ride completed." if payment_status == 'completed' else "Payment recorded. Waiting for driver confirmation."
        }, status=status.HTTP_200_OK)




class RiderRideDetailAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('driver', 'payment_detail').get(id=ride_id, user=request.user)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        # Timezone conversion to IST
        ist = pytz.timezone("Asia/Kolkata")
        start_time_ist = ride.start_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.start_time else None
        end_time_ist = ride.end_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.end_time else None

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
                    request.build_absolute_uri(driver.profile.url)
                    if hasattr(driver, 'profile') and driver.profile else None
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
                "total_paid": ride_price
            }

        return Response({
            "ride_id": ride.id,
            "from_location": ride.from_location,
            "to_location": ride.to_location,
            "distance_km": float(ride.distance_km),
            "start_time": start_time_ist,
            "end_time": end_time_ist,
            "driver": driver_info,
            "payment_summary": payment_summary
        }, status=status.HTTP_200_OK)
    


class RateDriverAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        rating = request.data.get('rating')
        review = request.data.get('review', '')

        # ✅ Validate rating presence
        if not rating:
            return Response({"detail": "Rating is required."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Validate ride
        try:
            ride = RideRequest.objects.get(id=ride_id, user=request.user, status='completed')
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or not completed."}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Check if already rated
        if hasattr(ride, 'driver_rating'):
            return Response({"detail": "You have already rated this ride."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rating_value = Decimal(rating)
            if rating_value < 1 or rating_value > 5:
                raise ValidationError("Rating must be between 1 and 5.")
        except:
            return Response({"detail": "Invalid rating value."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create rating
        DriverRating.objects.create(
            ride=ride,
            driver=ride.driver,
            rated_by=request.user,
            rating=rating_value,
            review=review
        )

        return Response({"message": "Rating submitted successfully."}, status=status.HTTP_201_CREATED)


# ride history
class RiderPastRideHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rider = request.user
        rides = RideRequest.objects.filter(
            user=rider,
            status__in=['completed', 'cancelled']
        ).select_related('payment_detail').order_by('-start_time')

        completed_rides = []
        cancelled_rides = []

        for ride in rides:
            serialized = RiderRideHistorySerializer(ride).data
            if ride.status == 'completed':
                completed_rides.append(serialized)
            elif ride.status == 'cancelled':
                cancelled_rides.append(serialized)

        return Response({
            "status": True,
            "message": "Ride history fetched successfully.",
            "completed_rides": completed_rides,
            "cancelled_rides": cancelled_rides
        }, status=status.HTTP_200_OK)


class RiderScheduledRidesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rider = request.user
        scheduled_rides = RideRequest.objects.filter(
            user=rider,
            status='pending',
            ride_type='scheduled'
        ).order_by('scheduled_time')

        serializer = RiderScheduledRideSerializer(scheduled_rides, many=True)
        return Response({
            "status": True,
            "message": "Scheduled rides fetched successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)



# promo codes
class ActivePromoCodesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()

        # Get active promo codes
        active_promos = PromoCode.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )

        promo_data = [
            {
                "code": promo.code,
                "description": promo.description
            }
            for promo in active_promos
        ]

        # Get user's favorite to-locations
        favorite_locations = FavoriteToLocation.objects.filter(user=request.user)
        favorites_data = FavoriteToLocationSerializer(favorite_locations, many=True).data

        return Response({
            "active_promos": promo_data,
            "favorite_to_locations": favorites_data  # ✅ always list (empty if none)
        }, status=status.HTTP_200_OK)

    

# corporate ride payment summary
class RideCorporatePaymentSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        user = request.user

        try:
            ride = RideRequest.objects.select_related('company').get(
                id=ride_id, user=user, status="accepted", ride_purpose="official"
            )
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or not eligible."}, status=404)

        company = ride.company
        credit = getattr(user, 'credit', None)

        if not credit or not credit.is_active:
            return Response({"detail": "No active employee credits found."}, status=400)

        total_amount = ride.offered_price or ride.estimated_price or 0
        available_credit = credit.available_credits()
        remaining_credit = available_credit - total_amount

        if remaining_credit < 0:
            return Response({"detail": "Insufficient credits for this ride."}, status=400)

        return Response({
            "ride_id": ride.id,
            "company_name": company.company_name if company else None,
            "total_amount": float(total_amount),
            "available_credit": float(available_credit),
            "credit_after_deduction": float(remaining_credit),
        })

class RideCorporateConfirmAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        user = request.user

        try:
            ride = RideRequest.objects.select_related('driver', 'company').get(
                id=ride_id, user=user, status="accepted", ride_purpose="official"
            )
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or not eligible."}, status=404)

        credit = getattr(user, 'credit', None)
        if not credit or not credit.is_active:
            return Response({"detail": "No active employee credits found."}, status=400)

        total_amount = ride.offered_price or ride.estimated_price or 0
        if total_amount <= 0:
            return Response({"detail": "Invalid ride amount."}, status=400)

        if credit.available_credits() < total_amount:
            return Response({"detail": "Insufficient employee credits."}, status=400)

        company = ride.company
        if not company:
            return Response({"detail": "Company not assigned for this ride."}, status=400)

        # Get active prepaid plan
        plan = CompanyPrepaidPlan.objects.filter(
            company=company,
            payment_status='success',
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        ).order_by('-end_date').first()

        if not plan:
            return Response({"detail": "No active corporate plan found."}, status=400)

        if plan.plan_credits_remaining < total_amount:
            return Response({"detail": "Insufficient total corporate plan credits."}, status=400)

        driver = ride.driver
        if not driver:
            return Response({"detail": "Driver not assigned."}, status=400)

        try:
            with transaction.atomic():
                # Create or update ride payment
                payment, _ = RidePaymentDetail.objects.get_or_create(
                    ride=ride,
                    defaults={
                        'user': user,
                        'grand_total': total_amount,
                        'payment_method': 'wallet',
                        'payment_status': 'pending',
                        'promo_code': None,
                        'promo_discount': 0,
                        'tip_amount': 0,
                        'driver_earnings': total_amount
                    }
                )

                # Deduct employee credits
                credit.used_credits += total_amount
                credit.save()

                # Update corporate plan employee spend
                plan.credits_spent_by_employees += int(total_amount)
                plan.save()

            return Response({
                "message": "Payment confirmed. Credits deducted from employee.",
                "amount_deducted": float(total_amount),
                "employee_remaining_credits": float(credit.available_credits()),
            }, status=200)

        except Exception as e:
            return Response({"detail": str(e)}, status=500)

class RiderProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'rider':
            return Response({"error": "User is not a rider."}, status=403)

        serializer = RiderProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data, status=200)

    def put(self, request):
        """
        Allows rider to update username, email and profile image.
        Phone number is read-only.
        """
        if request.user.role != 'rider':
            return Response({"error": "User is not a rider."}, status=403)

        serializer = RiderProfileSerializer(
            request.user,
            data=request.data,
            context={'request': request},
            partial=True  # so that only provided fields need to be validated
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)

        return Response(serializer.errors, status=400)


class RideReportListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        reports = RideReport.objects.all().order_by('-created_at')
        serializer = RideReportSerializer(reports, many=True)
        return Response({"status": True, "data": serializer.data}, status=status.HTTP_200_OK)
    
class SubmitRideReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RideReportSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Report submitted successfully.", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
class AddFavoriteToLocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FavoriteToLocationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)  # attach current user
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class EmployeeDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = request.user  # 1️⃣ Get from token

        # 2️⃣ Ensure user is an employee
        if employee.role != "employee":
            return Response({"detail": "Only employees can access this dashboard."}, status=403)

        # 3️⃣ Credits
        credit = getattr(employee, "credit", None)
        total_credits = credit.total_credits if credit else 0
        available_credits = credit.available_credits() if credit else 0

        # 4️⃣ Upcoming ride
        now = timezone.now()
        upcoming_ride = (
            RideRequest.objects.filter(
                Q(user=employee) | Q(employees=employee),
                status__in=["pending", "accepted", "scheduled", "draft"],
            )
            .filter(
                Q(ride_type="now", start_time__isnull=True)
                | Q(ride_type="scheduled", scheduled_time__gt=now)
            )
            .order_by("scheduled_time", "created_at")
            .first()
        )
        ride_data = RideRequestMiniSerializer(upcoming_ride).data if upcoming_ride else None

        # 5️⃣ Favorites
        fav_qs = FavoriteToLocation.objects.filter(user=employee)
        fav_data = FavoriteToLocationSerializer(fav_qs, many=True).data

        return Response({
            "employee_id": employee.id,
            "total_credits": str(total_credits),
            "available_credits": str(available_credits),
            "upcoming_ride": ride_data,
            "favorite_places": fav_data,
        })


class CancelRideByUserAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        if ride.user != request.user:
            return Response({"detail": "You are not allowed to cancel this ride."}, status=403)

        if ride.status in ['completed', 'cancelled']:
            return Response({"detail": "Cannot cancel a completed or already cancelled ride."}, status=400)

        ride.status = 'cancelled'
        ride.save()

        # ✅ Notify driver (if assigned)
        channel_layer = get_channel_layer()
        if ride.driver:
            driver_id = ride.driver.id
            group_name = f"user_{driver_id}"

            try:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "ride.cancelled_by_user",
                        "ride_id": ride.id,
                        "message": "Ride was cancelled by the rider.",
                        "user_name": request.user.username,
                        "user_id": request.user.id,
                    }
                )
                print("✅ Cancellation WebSocket sent to driver group:", group_name)
            except Exception as e:
                print("❌ Error sending cancellation message:", e)

        return Response({"message": "Ride cancelled successfully."}, status=200)

class DeleteFavoriteToLocationAPIView(generics.DestroyAPIView):
    queryset = FavoriteToLocation.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        favorite = super().get_object()
        if favorite.user != self.request.user:
            raise PermissionDenied("You don't have permission to delete this favorite location.")
        return favorite

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "Favorite location deleted successfully."}, status=status.HTTP_200_OK)
    

# chat history
class RideChatHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        # Ensure the ride exists and the user is either the rider or the driver
        ride = get_object_or_404(RideRequest, id=ride_id)

        if request.user != ride.user and request.user != ride.driver:
            return Response({"detail": "Not authorized to view this ride's messages."},
                            status=status.HTTP_403_FORBIDDEN)

        # Get all messages for this ride, ordered by timestamp
        messages = RideMessage.objects.filter(ride=ride).order_by('timestamp')
        serializer = RideMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class ActiveRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ride = RideRequest.objects.filter(
            user=request.user,
            status__in=['pending', 'accepted']
        ).order_by('-created_at').first()

        if not ride:
            return Response({"message": "No active ride found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ActiveRideSerializer(ride)
        return Response(serializer.data)