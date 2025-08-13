from django.shortcuts import render,get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .mixins import StandardResponseMixin
from rider_part.models import RideRequest
from django.db.models import Sum
from django.utils.timezone import make_aware,get_current_timezone
from rest_framework.parsers import MultiPartParser, FormParser
from . serializers import *
from django.db.models import Sum, Avg, Q
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
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
from rider_part.serializers import ActiveRideSerializer
# Create your views here.


class ToggleOnlineStatusAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({'status': 'error', 'message': 'Only drivers can toggle online status.'}, status=403)
        
        user.is_online = not user.is_online
        user.save()
        return Response({'status': 'success', 'is_online': user.is_online})
    
class DriverCashLimitAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({"error": "Only drivers have cash limit."}, status=403)

        return Response({
            "cash_payments_left": user.cash_payments_left,
            "is_online": user.is_online
        })

    
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
            city=city,ride_purpose  = 'personal'  # Only personal rides for now
        ).order_by('-id')

        if not rides.exists():
            return Response({"status": True, "message": "No rides available.", "data": []}, status=status.HTTP_200_OK)

        serializer = RideNowDestinationSerializer(rides, many=True)
        return Response({
            "status": True,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    
class AvailableScheduledRidesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        city_name = request.data.get('city_name')

        if not city_name:
            return Response({"error": "City name is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response({"error": "City not found."}, status=status.HTTP_404_NOT_FOUND)

        # Current time + 1 hour (exclude rides starting within the next 1 hour)
        now_plus_1_hour = timezone.now() + timedelta(hours=1)

        rides = RideRequest.objects.filter(
            ride_type='scheduled',
            status='pending',
            city=city,
            scheduled_time__gt=now_plus_1_hour  # only rides that are more than 1 hour away
        ).exclude(
            declined_by_drivers__driver=request.user
        )

        if not rides.exists():
            return Response({"message": "No scheduled rides available."}, status=status.HTTP_200_OK)

        serializer = RideNowDestinationSerializer(rides, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class RideRequestDetailAPIView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.prefetch_related('ride_stops').get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"error": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideRequestDetailSerializer(ride, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeclineRideAPIView(StandardResponseMixin,APIView):
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


class AcceptRideAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, status='pending')
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or already accepted"}, status=status.HTTP_404_NOT_FOUND)

        # Assign the driver and update status
        ride.driver = request.user
        ride.status = 'accepted'
        ride.save()

        serializer = RideAcceptedDetailSerializer(ride)

        # 🔔 Prepare to send WebSocket notification
        channel_layer = get_channel_layer()
        rider_id = ride.user.id
        group_name = f"user_{rider_id}"

        print(f"🔄 Ride accepted by driver {request.user.id} ({request.user.username})")
        print(f"📡 Sending WebSocket message to group: {group_name}")

        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "ride.accepted",  # This maps to ride_accepted() in consumer
                    "ride_id": ride.id,
                    "message": "Your ride has been accepted by a driver.",
                    "driver_name": request.user.username,
                    "driver_id": request.user.id,
                }
            )
            print("✅ WebSocket message sent successfully.")
        except Exception as e:
            print("❌ Error sending WebSocket message:", e)

        return Response({
            "message": "Ride accepted and driver assigned successfully.",
            "ride_details": serializer.data
        }, status=status.HTTP_200_OK)

class CancelRideAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found"}, status=status.HTTP_404_NOT_FOUND)

        if ride.driver != request.user:
            return Response({"detail": "You are not allowed to cancel this ride."}, status=403)

        if ride.status in ['completed', 'cancelled']:
            return Response({"detail": "Cannot cancel a completed or already cancelled ride."}, status=400)

        ride.status = 'cancelled'
        ride.save()

        # ✅ Send WebSocket cancel event to rider
        channel_layer = get_channel_layer()
        rider_id = ride.user.id
        group_name = f"user_{rider_id}"

        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "ride.cancelled",
                    "ride_id": ride.id,
                    "message": "Your ride was cancelled by the driver.",
                    "driver_name": request.user.username,
                    "driver_id": request.user.id,
                }
            )
            print("✅ Cancellation WebSocket sent to group:", group_name)
        except Exception as e:
            print("❌ Error sending cancellation message:", e)

        return Response({"message": "Ride cancelled successfully."}, status=200)
    
class RideDetailAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('user').prefetch_related('ride_stops').get(
                id=ride_id, 
                status='accepted',
                driver=request.user  # Optional: ensures only assigned driver can view
            )
            if ride.driver != request.user:
                return Response({'detail': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        except RideRequest.DoesNotExist:
            return Response({'detail': 'Ride not found or not yet accepted or completed'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RideDetailSerializer(ride, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class RideDetailView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id,status='accepted',driver=request.user)
            if ride.driver != request.user:
                return Response({'detail': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        except RideRequest.DoesNotExist:
            return Response({'detail': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RidePriceDetailSerializer(ride)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


# begin ride
class SetRideStartTimeAPIView(StandardResponseMixin,APIView):
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


class SetRideEndTimeAPIView(StandardResponseMixin,APIView):
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
class GenerateRideOTPView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        otp_code = str(random.randint(100000, 999999))

        try:
            ride = RideRequest.objects.get(id=ride_id, status="accepted", driver=request.user)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found"}, status=404)

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
            f"ride_{ride.id}",  # Or use a dynamic group name if needed
            {
                "type": "send.otp",
                "otp": otp_code
            }
        )

        return Response({"message": f"OTP {otp_code} sent to WebSocket."})

    

class VerifyRideOTPView(StandardResponseMixin,APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        otp_entered = request.data.get("otp")
        try:
            ride = RideRequest.objects.get(id=ride_id, driver=request.user)
            otp_obj = ride.otp
        except (RideRequest.DoesNotExist, RideOTP.DoesNotExist):
            return Response({"detail": "Ride or OTP not found"}, status=404)

        if otp_obj.is_verified:
            return Response({"message": "OTP already verified"}, status=400)

        if otp_obj.is_expired():
            return Response({"detail": "OTP has expired"}, status=400)

        if otp_obj.code != otp_entered:
            return Response({"detail": "Invalid OTP"}, status=400)

        # OTP is valid
        otp_obj.is_verified = True
        otp_obj.save()
        ride.status = 'accepted'
        ride.save()

        return Response({"message": "OTP verified"})

class RideSummaryForDriverAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id, status="accepted", driver=request.user)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or ride completed"}, status=status.HTTP_404_NOT_FOUND)

        rider = ride.user
        ist = pytz.timezone("Asia/Kolkata")

        start_time_ist = ride.start_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.start_time else None
        end_time_ist = ride.end_time.astimezone(ist).strftime('%Y-%m-%d %I:%M %p') if ride.end_time else None

        duration = None
        if ride.start_time and ride.end_time:
            duration = ride.end_time - ride.start_time

        # Try to get payment details
        payment_info = None
        try:
            payment = RidePaymentDetail.objects.get(ride=ride)
            payment_info = {
                "grand_total": float(payment.grand_total),
                "promo_discount": float(payment.promo_discount),
                "tip_amount": float(payment.tip_amount),
                "wallet": float(payment.driver_earnings),
                "payment_method": payment.payment_method,
                "payment_status": payment.payment_status,
            }
        except RidePaymentDetail.DoesNotExist:
            # fallback minimal payment info
            ride_price = ride.offered_price if ride.offered_price else ride.estimated_price
            payment_info = {
                "grand_total": float(ride_price) if ride_price else None,
                "payment_status": "pending"
            }

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
            "ride_summary": {
                "distance_km": float(ride.distance_km),
                "price": float(ride.offered_price if ride.offered_price else ride.estimated_price)
            },
            "payment_summary": payment_info
        }, status=status.HTTP_200_OK)


# update payment status
class UpdateRidePaymentStatusAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ride_id = request.data.get('ride_id')
        payment_status = request.data.get('payment_status')

        if not ride_id or not payment_status:
            return Response(
                {"detail": "Ride ID and payment status are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if payment_status not in ['pending', 'completed', 'failed', 'cancelled']:
            return Response(
                {"detail": "Invalid payment status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ride = RideRequest.objects.get(id=ride_id, driver=request.user)
        except RideRequest.DoesNotExist:
            return Response(
                {"detail": "Ride not found or you are not the assigned driver."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            payment_detail = RidePaymentDetail.objects.get(ride=ride)
        except RidePaymentDetail.DoesNotExist:
            return Response(
                {"detail": "Payment details not found for this ride."},
                status=status.HTTP_404_NOT_FOUND
            )

        if payment_detail.payment_status in ['completed', 'cancelled']:
            return Response(
                {"detail": "Cannot update payment status once completed or cancelled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ If cash method and status is 'completed', decrement driver's cash payment count
        if payment_status == 'completed' and payment_detail.payment_method == 'cash':
            driver = request.user
            if driver.cash_payments_left > 0:
                driver.cash_payments_left -= 1
                driver.save()
            else:
                return Response(
                    {"detail": "You have no cash payments left."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Update payment status
        payment_detail.payment_status = payment_status
        payment_detail.save()

        # ✅ If completed, update ride status and conditionally add wallet transaction
        if payment_status == 'completed':
            # Mark ride as completed
            ride.status = 'completed'
            ride.save()

            # Only credit wallet if NOT a cash payment
            if payment_detail.payment_method != 'cash':
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

                # Create wallet transaction
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
            "message": (
                "Payment status and ride status updated."
                + (" Driver wallet credited." if payment_detail.payment_method != 'cash' else " (Cash payment - wallet not affected).")
                if payment_status == 'completed' else "Payment status updated."
            )
        }, status=status.HTTP_200_OK)


class DriverRideEarningDetailAPIView(UpdateRidePaymentStatusAPIView,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('user').get(
                id=ride_id, driver=request.user, status='completed'
            )
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found or not completed."}, status=status.HTTP_404_NOT_FOUND)

        try:
            payment = RidePaymentDetail.objects.get(ride=ride)
        except RidePaymentDetail.DoesNotExist:
            return Response({"detail": "Payment details not found."}, status=status.HTTP_404_NOT_FOUND)

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
    

class DriverNameAPIView(UpdateRidePaymentStatusAPIView,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({'detail': 'Only drivers can access this endpoint.'}, status=403)

        serializer = DriverProfileSerializer(user, context={'request': request})
        return Response(serializer.data, status=200)
    

# ride history
class DriverPastRideHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = request.user

        # Past rides
        rides = RideRequest.objects.filter(
            driver=driver,
            status__in=['completed', 'cancelled']
        ).select_related('payment_detail').order_by('-start_time')

        completed_rides = []
        cancelled_rides = []

        for ride in rides:
            serialized = DriverRideHistorySerializer(ride).data
            if ride.status == 'completed':
                completed_rides.append(serialized)
            elif ride.status == 'cancelled':
                cancelled_rides.append(serialized)

        # Upcoming scheduled rides
        upcoming_rides_qs = RideRequest.objects.filter(
            driver=driver,
            status='accepted',
            ride_type='scheduled',
            scheduled_time__gt=timezone.now()
        ).order_by('scheduled_time')

        upcoming_rides = DriverRideHistorySerializer(upcoming_rides_qs, many=True).data

        return Response({
            "status": True,
            "message": "Ride history fetched successfully.",
            "completed_rides": completed_rides,
            "cancelled_rides": cancelled_rides,
            "upcoming_rides": upcoming_rides
        }, status=status.HTTP_200_OK)




class DriverScheduledRidesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        driver = request.user
        scheduled_rides = RideRequest.objects.filter(
            driver=driver,
            status='accepted',
            ride_type='scheduled'
        ).order_by('scheduled_time')

        serializer = DriverScheduledRideSerializer(scheduled_rides, many=True)
        return Response({
            "status": True,
            "message": "Upcoming scheduled rides fetched successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)



class DriverEarningsSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"detail": "Only drivers can access this data."}, status=403)

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

        # ✅ Total earnings from all wallet transactions
        total_earnings = DriverWalletTransaction.objects.filter(
            driver=user
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        summary = {
            "today_earnings": float(get_earning(start_today, end_today)),
            "yesterday_earnings": float(get_earning(start_yesterday, end_yesterday)),
            "this_week_earnings": float(get_earning(start_of_week, now)),
            "this_month_earnings": float(get_earning(start_of_month, now)),
            "total_earnings": float(total_earnings),
            "remaining_cash_limit": user.cash_payments_left
        }

        return Response({
            "success": True,
            "message": "success",
            "data": summary
        }, status=200)
    

from rest_framework.parsers import MultiPartParser, FormParser

class DriverProfileAPIView(UpdateRidePaymentStatusAPIView, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # For file uploads

    def get(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"detail": "Access denied. Only drivers allowed."}, status=403)

        vehicle_info = getattr(user, 'vehicle_info', None)

        profile_url = None
        if user.profile and hasattr(user.profile, 'url'):
            profile_url = request.build_absolute_uri(user.profile.url)

        return Response({
            "username": user.username,
            "email": user.email,
            "profile_image": profile_url,
            "vehicle_info": {
                "id": vehicle_info.id if vehicle_info else None,
                "vehicle_number": vehicle_info.vehicle_number if vehicle_info else None,
                "car_name": f"{vehicle_info.car_company} {vehicle_info.car_model}" if vehicle_info else None
            }
        })

    def put(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"detail": "Access denied. Only drivers allowed."}, status=403)

        username = request.data.get('username')
        email = request.data.get('email')
        profile_image = request.FILES.get('profile_image')

        if username:
            user.username = username
        if email:
            user.email = email
        if profile_image:
            user.profile = profile_image  # Assuming `profile` is an ImageField in CustomUser

        user.save()

        profile_url = None
        if user.profile and hasattr(user.profile, 'url'):
            profile_url = request.build_absolute_uri(user.profile.url)

        return Response({
            "message": "Profile updated successfully",
            "username": user.username,
            "email": user.email,
            "profile_image": profile_url
        })

# vehilce docs

class DriverDocumentAPIView(UpdateRidePaymentStatusAPIView,APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        try:
            document_info = request.user.document_info
        except DriverDocumentInfo.DoesNotExist:
            return Response({"detail": "Documents not uploaded yet."}, status=404)

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


class DriverStatsAPIView(UpdateRidePaymentStatusAPIView,APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != 'driver':
            return Response({'detail': 'Access denied. Only drivers allowed.'}, status=403)

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
                "today_earnings": float(earnings_today),
                "today_ride_count": ride_count_today,
                "average_rating": round(avg_rating, 1),

        }, status=200)
    

class DriverCashOutRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"error": "Only drivers can request withdrawal."}, status=403)

        amount = request.data.get('amount')
        if not amount:
            return Response({"error": "Amount is required."}, status=400)

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except:
            return Response({"error": "Invalid amount."}, status=400)

        # Optional: Check if they are eligible to withdraw this much
        total_earnings = DriverWalletTransaction.objects.filter(driver=user).aggregate(total=Sum('amount'))['total'] or 0.0
        if amount > total_earnings:
            return Response({"error": "Withdrawal amount exceeds total earnings."}, status=400)

        CashOutRequest.objects.create(driver=user, amount=amount)
        return Response({"message": "Cash out request submitted."}, status=201)
    

# corporate available ride API
class CorporateAvailableRidesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        city_name = request.data.get('city_name')

        # ✅ Ensure city is provided
        if not city_name:
            return Response({"status": False, "message": "City name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Fetch city object
        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response({"status": False, "message": "City not found."}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Ensure only drivers are allowed
        if user.role != 'driver':
            return Response({"status": False, "message": "Only drivers can access this API."}, status=status.HTTP_403_FORBIDDEN)

        # ✅ Reject if driver is not corporate
        if user.driver_type == 'normal':
            return Response({"status": False, "message": "You are not a corporate driver."}, status=status.HTTP_403_FORBIDDEN)

        # ✅ Determine the company filter logic
        if user.is_universal_corporate_driver:
            # Universal driver → all approved corporate rides in that city
            rides = RideRequest.objects.filter(
                ride_type='now',
                status='pending',
                city=city,
                company__isnull=False,
            ).filter(Q(ride_purpose="official") | Q(ride_purpose="corporate_admin"))
        else:
            # Assigned companies only
            assigned_companies = user.corporate_companies.all()
            if not assigned_companies.exists():
                return Response({"status": False, "message": "No corporate companies assigned to you."}, status=status.HTTP_403_FORBIDDEN)

            rides = RideRequest.objects.filter(
                ride_type='now',
                status='pending',
                city=city,
                company__in=assigned_companies,
            ).filter(Q(ride_purpose="official") | Q(ride_purpose="corporate_admin"))

        if not rides.exists():
            return Response({"status": True, "message": "No corporate rides available.", "data": []}, status=status.HTTP_200_OK)

        serializer = RideNowDestinationSerializer(rides, many=True)
        return Response({
            "status": True,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class DriverRideDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        driver = request.user
        ride = get_object_or_404(RideRequest, id=ride_id, driver=driver)

        # Rider details
        rider = ride.user
        profile_url = request.build_absolute_uri(rider.profile.url) if rider.profile else None

        # Get start time logic
        if ride.ride_type == 'scheduled' and ride.scheduled_time:
            start_time = localtime(ride.scheduled_time).strftime("%Y-%m-%d %I:%M %p")
        else:
            start_time = localtime(ride.start_time).strftime("%Y-%m-%d %I:%M %p") if ride.start_time else None

        # Stops
        stops = list(ride.ride_stops.values("location", "latitude", "longitude", "order"))

        # Credited amount from DriverWalletTransaction
        credited_amount = DriverWalletTransaction.objects.filter(
            driver=driver,
            ride=ride
        ).aggregate(total=models.Sum("amount"))["total"]

        # Payment method
        payment_method = ride.payment_detail.payment_method if hasattr(ride, "payment_detail") else None

        # Duration calculation
        duration = None
        if ride.start_time and ride.end_time:
            diff = ride.end_time - ride.start_time
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            duration = f"{hours}h {minutes}m" if hours else f"{minutes}m"

        # Rating & Review
        rating_data = None
        driver_rating = ride.driver_ratings.filter(driver=driver).first()
        if driver_rating:
            rating_data = {
                "rating": float(driver_rating.rating),
                "review": driver_rating.review
            }

        data = {
            "ride_id": ride.id,
            "from_location": {
                "address": ride.from_location,
                "latitude": float(ride.from_latitude),
                "longitude": float(ride.from_longitude)
            },
            "to_location": {
                "address": ride.to_location,
                "latitude": float(ride.to_latitude),
                "longitude": float(ride.to_longitude)
            },
            "stops": stops,
            "start_time": start_time,
            "distance_km": float(ride.distance_km) if ride.distance_km else None,
            "credited_amount": float(credited_amount) if credited_amount else 0.0,
            "payment_method": payment_method,
            "duration": duration,
            "rider": {
                "username": rider.username,
                "profile_image": profile_url,
                "rating_review": rating_data
            }
        }

        return Response({
            "status": True,
            "message": "Ride details fetched successfully.",
            "data": data
        }, status=status.HTTP_200_OK)
    

class DriverActiveRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rides = RideRequest.objects.filter(
            driver=request.user,
            status='accepted'
        ).select_related('otp')

        serializer = ActiveRideSerializer(rides, many=True)
        return Response(serializer.data)