from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rider_part.models import RideRequest
from django.db.models import Sum
from django.utils.timezone import make_aware,get_current_timezone
from rest_framework.parsers import MultiPartParser, FormParser
from . serializers import *
from django.db.models import Sum, Avg, Q
from datetime import datetime
from decimal import Decimal
from rest_framework import status
from auth_api.models import DriverRating
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import localtime
import pytz
from . models import *
from admin_part.models import PlatformSetting
from rider_part.models import DriverWalletTransaction, RideRequest, RidePaymentDetail
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
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
            return Response({"status": False, "message": "City name is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response({"status": False, "message": "City not found."}, status=status.HTTP_404_NOT_FOUND)

        rides = RideRequest.objects.filter(
            ride_type='now',
            status='pending',
            city=city
        )

        if not rides.exists():
            return Response({"status": True, "message": "No rides available.", "data": []}, status=status.HTTP_200_OK)

        serializer = RideNowDestinationSerializer(rides, many=True)
        return Response({
            "status": True,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    

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
            serializer = RideDetailSerializer(ride,context={'request': request})
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

        # Check if OTP exists and is verified
        try:
            otp = ride.otp  # related_name='otp'
            if not otp.is_verified:
                return Response({"detail": "OTP has not been verified. Ride cannot start."},
                                status=status.HTTP_403_FORBIDDEN)
        except RideOTP.DoesNotExist:
            return Response({"detail": "OTP verification is required before starting the ride."},
                            status=status.HTTP_403_FORBIDDEN)

        # Prevent setting start time again
        if ride.start_time:
            return Response({"detail": "Start time already set."}, status=status.HTTP_400_BAD_REQUEST)

        # Capture and return IST time
        current_time = timezone.now()
        ride.start_time = current_time
        ride.save()

        ist_time = current_time.astimezone(pytz.timezone("Asia/Kolkata"))

        return Response({
            "ride_id": ride.id,
            "start_time": current_time,
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
    

# Generate OTP and sending to the rider
class GenerateRideOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        otp_code = str(random.randint(100000, 999999))

        try:
            ride = RideRequest.objects.get(id=ride_id, driver=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found"}, status=404)

        # Save or update the OTP with fresh created_at timestamp
        RideOTP.objects.update_or_create(
            ride=ride,
            defaults={
                'code': otp_code,
                'created_at': timezone.now(),
                'is_verified': False,
            }
        )

        # Send OTP via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "ride_user_test",  # Or use a dynamic group name if needed
            {
                "type": "send.otp",
                "otp": otp_code
            }
        )

        return Response({"message": f"OTP {otp_code} sent to WebSocket."})

    

class VerifyRideOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        otp_entered = request.data.get("otp")
        try:
            ride = RideRequest.objects.get(id=ride_id, driver=request.user)
            otp_obj = ride.otp
        except (RideRequest.DoesNotExist, RideOTP.DoesNotExist):
            return Response({"error": "Ride or OTP not found"}, status=404)

        if otp_obj.is_verified:
            return Response({"message": "OTP already verified"}, status=400)

        if otp_obj.is_expired():
            return Response({"error": "OTP has expired"}, status=400)

        if otp_obj.code != otp_entered:
            return Response({"error": "Invalid OTP"}, status=400)

        # OTP is valid
        otp_obj.is_verified = True
        otp_obj.save()
        ride.status = 'accepted'
        ride.save()

        return Response({"message": "OTP verified"})

class RideSummaryForDriverAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, driver=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found or you're not the assigned driver."}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = RidePaymentDetail.objects.get(ride=ride)
        except RidePaymentDetail.DoesNotExist:
            return Response({"error": "Payment details not found."}, status=status.HTTP_404_NOT_FOUND)

        rider = ride.user
        ist = pytz.timezone("Asia/Kolkata")

        # Convert to IST if exists
        start_time_ist = ride.start_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.start_time else None
        end_time_ist = ride.end_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.end_time else None

        duration = None
        if ride.start_time and ride.end_time:
            duration = ride.end_time - ride.start_time

        return Response({
            "rider": {
                "id": rider.id,
                "name": f"{rider.username}".strip(),
                "phone": rider.phone_number,
            },
            "locations": {
                "from": ride.from_location,
                "to": ride.to_location,
            },
            "timing": {
                "start_time": start_time_ist,
                "end_time": end_time_ist,
                "duration": str(duration) if duration else None,
            },
            "payment_summary": {
                "grand_total": float(payment.grand_total),
                "promo_discount": float(payment.promo_discount),
                "tip_amount": float(payment.tip_amount),
                "wallet": float(payment.driver_earnings),
                "payment_method": payment.payment_method,
                "payment_status": payment.payment_status,
            }
        }, status=status.HTTP_200_OK)


# update payment status
class UpdateRidePaymentStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ride_id = request.data.get('ride_id')
        payment_status = request.data.get('payment_status')

        if not ride_id or not payment_status:
            return Response({"error": "Ride ID and payment status are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if payment_status not in ['pending', 'completed', 'failed', 'cancelled']:
            return Response({"error": "Invalid payment status."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            ride = RideRequest.objects.get(id=ride_id, driver=request.user)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found or you are not the assigned driver."},
                            status=status.HTTP_404_NOT_FOUND)

        try:
            payment_detail = RidePaymentDetail.objects.get(ride=ride)
        except RidePaymentDetail.DoesNotExist:
            return Response({"error": "Payment details not found for this ride."},
                            status=status.HTTP_404_NOT_FOUND)

        if payment_detail.payment_status in ['completed', 'cancelled']:
            return Response({"error": "Cannot update payment status once completed or cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)

        # ✅ If cash method and status is 'completed', decrement counter
        if payment_status == 'completed' and payment_detail.payment_method == 'cash':
            driver = request.user
            if driver.cash_payments_left > 0:
                driver.cash_payments_left -= 1
                driver.save()
            else:
                return Response({"error": "You have no cash payments left."},
                                status=status.HTTP_400_BAD_REQUEST)

        # ✅ Update payment status
        payment_detail.payment_status = payment_status
        payment_detail.save()

        # ✅ If completed, update ride status and wallet
        if payment_status == 'completed':
            # Mark ride as completed
            ride.status = 'completed'
            ride.save()

            driver = request.user
            base_earning = payment_detail.driver_earnings
            tip = payment_detail.tip_amount or Decimal('0.00')

            # Fetch active platform fee
            platform_fee = Decimal('0.00')
            active_fee = PlatformSetting.objects.filter(is_active=True).order_by('-updated_at').first()
            if active_fee:
                if active_fee.fee_type == 'percentage':
                    platform_fee = (active_fee.fee_value / Decimal('100')) * base_earning
                else:
                    platform_fee = active_fee.fee_value

            # Final earnings
            net_earning = base_earning - platform_fee + tip

            DriverWalletTransaction.objects.create(
                driver=driver,
                ride=ride,
                amount=net_earning,
                transaction_type='ride_earning',
                description=f"Earnings for Ride #{ride.id} | Base: ₹{base_earning} - Platform Fee: ₹{platform_fee} + Tip: ₹{tip}"
            )

        return Response({
            "success": True,
            "ride_id": ride.id,
            "payment_status": payment_status,
            "message": "Payment status and ride status updated. Driver wallet credited." if payment_status == 'completed' else "Payment status updated."
        }, status=status.HTTP_200_OK)


class DriverRideEarningDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('user').get(
                id=ride_id, driver=request.user, status='completed'
            )
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found or not completed."}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = RidePaymentDetail.objects.get(ride=ride)
        except RidePaymentDetail.DoesNotExist:
            return Response({"error": "Payment details not found."}, status=status.HTTP_404_NOT_FOUND)

        # Duration calculation
        duration = None
        if ride.start_time and ride.end_time:
            duration = ride.end_time - ride.start_time

        ist = pytz.timezone("Asia/Kolkata")
        start_time_ist = ride.start_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.start_time else None
        end_time_ist = ride.end_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.end_time else None
        # Try to get rider rating
        rating_data = None
        try:
            rating = DriverRating.objects.get(ride=ride, driver=request.user)
            rating_data = {
                "rating": float(rating.rating),
                "review": rating.review,
            }
        except DriverRating.DoesNotExist:
            pass

        # Handle cash vs non-cash payment
        if payment.payment_method == 'cash':
            ride_price = ride.offered_price if ride.offered_price else ride.estimated_price
            payment_info = {
                "payment_method": "cash",
                "received_amount": float(ride_price) if ride_price else None,
                "note": "Payment was made in cash. No digital summary available."
            }
        else:
            # Get active platform setting
            platform_fee = PlatformSetting.objects.filter(is_active=True).first()

            fee_amount = Decimal(0)
            fee_type = None
            fee_value = None

            if platform_fee:
                fee_type = platform_fee.fee_type
                fee_value = platform_fee.fee_value
                if fee_type == 'percentage':
                    fee_amount = (payment.driver_earnings * fee_value) / 100
                else:
                    fee_amount = fee_value

            # Final amount after deduction + tips
            total_received = payment.driver_earnings - fee_amount + payment.tip_amount

            payment_info = {
                "driver_earnings": float(payment.driver_earnings),
                "tip_amount": float(payment.tip_amount),
                "platform_fee_type": fee_type,
                "platform_fee_value": float(fee_value) if fee_value else None,
                "platform_fee_deducted": float(fee_amount),
                "total_received_by_driver": float(total_received),
            }

        return Response({
            "rider": {
                "id": ride.user.id,
                "username": ride.user.username,
                "email": ride.user.email,
                "profile_image": (
                    request.build_absolute_uri(ride.user.profile.url)
                    if hasattr(ride.user, 'profile') and ride.user.profile and request
                    else None
                ),
            },
            "ride_info": {
                "distance_km": float(ride.distance_km),
                "start_time": start_time_ist,
                "end_time": end_time_ist,
                "duration": str(duration) if duration else None,
            },
            "payment_summary": payment_info,
            "rider_rating": rating_data
        }, status=status.HTTP_200_OK)
    

class DriverNameAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({'error': 'Only drivers can access this endpoint.'}, status=403)

        serializer = DriverProfileSerializer(user, context={'request': request})
        return Response(serializer.data, status=200)
    

# ride history
class DriverRideHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = request.user
        rides = RideRequest.objects.filter(
            driver=driver,
            status='completed'
        ).select_related('payment_detail').order_by('-start_time')

        serializer = DriverRideHistorySerializer(rides, many=True)
        return Response({
            "status": True,
            "message": "Ride history fetched successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class DriverEarningsSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"error": "Only drivers can access this data."}, status=403)

        ist = pytz.timezone("Asia/Kolkata")
        now = timezone.now().astimezone(ist)
        today = now.date()

        # Define time ranges in IST
        def start_of(day):
            return timezone.make_aware(datetime.combine(day, datetime.min.time()), timezone=ist)

        def end_of(day):
            return timezone.make_aware(datetime.combine(day, datetime.max.time()), timezone=ist)

        start_today = start_of(today)
        end_today = end_of(today)

        start_yesterday = start_of(today - timedelta(days=1))
        end_yesterday = end_of(today - timedelta(days=1))

        start_of_week = start_of(today - timedelta(days=today.weekday()))
        start_of_month = start_of(today.replace(day=1))

        def get_earning(start, end):
            return DriverWalletTransaction.objects.filter(
                driver=user,
                created_at__range=(start, end)
            ).aggregate(total=Sum('amount'))['total'] or 0.0

        summary = {
            "today_earnings": float(get_earning(start_today, end_today)),
            "yesterday_earnings": float(get_earning(start_yesterday, end_yesterday)),
            "this_week_earnings": float(get_earning(start_of_week, now)),
            "this_month_earnings": float(get_earning(start_of_month, now)),
            "remaining_cash_limit": user.cash_payments_left
        }

        return Response({"success": True, "data": summary}, status=200)
    

class DriverProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"error": "Access denied. Only drivers allowed."}, status=403)

        vehicle_info = getattr(user, 'vehicle_info', None)

        profile_url = None
        if user.profile and hasattr(user.profile, 'url'):
            profile_url = request.build_absolute_uri(user.profile.url)

        data = {
            "username": user.username,
            "email": user.email,
            "profile_image": profile_url,
            "vehicle_info": {
                "id": vehicle_info.id if vehicle_info else None,
                "vehicle_number": vehicle_info.vehicle_number if vehicle_info else None,
                "car_name": f"{vehicle_info.car_company} {vehicle_info.car_model}" if vehicle_info else None
            }
        }

        return Response({"success": True, "data": data})
    
# vehilce docs

class DriverDocumentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        try:
            document_info = request.user.document_info
        except DriverDocumentInfo.DoesNotExist:
            return Response({"error": "Documents not uploaded yet."}, status=404)

        serializer = DriverDocumentSerializer(document_info, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        try:
            document_info = request.user.document_info
        except DriverDocumentInfo.DoesNotExist:
            return Response({"error": "Documents not found."}, status=404)

        vehicle_insurance = request.FILES.get("vehicle_insurance")
        if not vehicle_insurance:
            return Response({"error": "Only vehicle_insurance can be updated."}, status=400)

        document_info.vehicle_insurance = vehicle_insurance
        document_info.save()

        serializer = DriverDocumentSerializer(document_info, context={'request': request})
        return Response(serializer.data, status=200)
    
class DriverStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({'error': 'Access denied. Only drivers allowed.'}, status=403)

        ist = get_current_timezone()
        today = datetime.now(ist).date()
        start_of_today = make_aware(datetime.combine(today, datetime.min.time()), timezone=ist)
        end_of_today = make_aware(datetime.combine(today, datetime.max.time()), timezone=ist)

        # ✅ Total Earnings Today (via wallet transactions)
        earnings_today = DriverWalletTransaction.objects.filter(
            driver=user,
            created_at__range=(start_of_today, end_of_today)
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        # ✅ Total Completed Rides Today
        ride_count_today = RideRequest.objects.filter(
            driver=user,
            status='completed',
            end_time__range=(start_of_today, end_of_today)
        ).count()

        # ✅ Average Rating
        avg_rating = DriverRating.objects.filter(driver=user).aggregate(avg=Avg('rating'))['avg'] or 0.0

        return Response({
            "success": True,
            "data": {
                "today_earnings": float(earnings_today),
                "today_ride_count": ride_count_today,
                "average_rating": round(avg_rating, 1),
            }
        }, status=200)