from django.shortcuts import render,get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .mixins import StandardResponseMixin
from rider_part.models import RideRequest
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.db.models import Sum
from django.utils.timezone import make_aware,get_current_timezone
from rest_framework.parsers import MultiPartParser, FormParser
from . serializers import *
from django.db.models import Sum, Avg, Q
from datetime import datetime
from notifications.fcm import send_fcm_notification
from decimal import Decimal
from django.utils import timezone
from auth_api.models import DriverVehicleInfo
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
            return Response(
                {"status": False, "message": "City name is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            city = City.objects.get(name__iexact=city_name)
        except City.DoesNotExist:
            return Response(
                {"status": False, "message": "City not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Get driver's vehicle type
        try:
            driver_vehicle_type = request.user.vehicle_info.vehicle_type
        except DriverVehicleInfo.DoesNotExist:
            return Response(
                {"status": False, "message": "Driver vehicle information not found."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Base filter
        rides = RideRequest.objects.filter(
            ride_type='now',
            status='pending',
            city=city,
            ride_purpose='personal',
            vehicle_type=driver_vehicle_type
        )

        # Filter women-only rides if driver is female
        if request.user.gender == 'female':
            # female drivers can take all rides including women_only
            rides = rides.filter(models.Q(women_only=False) | models.Q(women_only=True))
        else:
            # male/other drivers should not see women-only rides
            rides = rides.filter(women_only=False)

        rides = rides.order_by('-id')

        if not rides.exists():
            return Response(
                {"status": True, "message": "No rides available.", "data": []}, 
                status=status.HTTP_200_OK
            )

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

        # Get driver's vehicle type
        try:
            driver_vehicle_type = request.user.vehicle_info.vehicle_type
        except DriverVehicleInfo.DoesNotExist:
            return Response(
                {"error": "Driver vehicle information not found."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Current time + 1 hour (exclude rides starting within the next 1 hour)
        now_plus_1_hour = timezone.now() + timedelta(hours=1)

        # Base queryset
        rides = RideRequest.objects.filter(
            ride_type='scheduled',
            status='pending',
            city=city,
            vehicle_type=driver_vehicle_type,
            scheduled_time__gt=now_plus_1_hour
        ).exclude(
            declined_by_drivers__driver=request.user
        )

        # Filter women-only rides
        if request.user.gender == 'female':
            # female drivers can take all rides including women-only
            rides = rides.filter(Q(women_only=False) | Q(women_only=True))
        else:
            # male/other drivers should not see women-only rides
            rides = rides.filter(women_only=False)

        rides = rides.order_by('-scheduled_time')

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

        # 🔔 WebSocket notification
        channel_layer = get_channel_layer()
        rider_id = ride.user.id
        group_name = f"user_{rider_id}"

        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "ride.accepted",
                    "ride_id": ride.id,
                    "message": "Your ride has been accepted by a driver.",
                    "driver_name": request.user.username,
                    "driver_id": request.user.id,
                }
            )
            print("✅ WebSocket message sent successfully.")
        except Exception as e:
            print("❌ Error sending WebSocket message:", e)

        # 🔔 FCM notification
        try:
            from notifications.fcm import send_fcm_notification  # wherever you placed the function

            send_fcm_notification(
                user=ride.user,
                title="Ride Accepted 🚖",
                body=f"Your ride has been accepted by {request.user.username}.",
                data={
                    "ride_id": str(ride.id),
                    "driver_id": str(request.user.id),
                    "driver_name": request.user.username,
                    "status": "accepted"
                }
            )
            print("✅ FCM notification sent successfully.")
        except Exception as e:
            print("❌ Error sending FCM notification:", e)

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
            return Response({"detail": "Ride not found"}, status=status.HTTP_404_NOT_FOUND)

        if ride.driver != request.user:
            return Response({"detail": "You are not allowed to cancel this ride."}, status=403)

        if ride.status in ['completed', 'cancelled']:
            return Response({"detail": "Cannot cancel a completed or already cancelled ride."}, status=400)

       
        driver = request.user
        cancellation_fee_applied = 0
        # If driver has cancellations left
        if driver.driver_cancellations_left > 0:
            driver.driver_cancellations_left -= 1
            driver.save()
            print(f"✅ Driver {driver.id} free cancellations left: {driver.driver_cancellations_left}")
        else:
            try:
                platform_setting = PlatformSetting.objects.filter(fee_reason="cancellation fees", is_active=True).first()
                ride_amount = ride.ride_amount or 0  

                if platform_setting.fee_type == "percentage":
                    cancellation_fee_applied = (ride_amount * platform_setting.fee_value) / 100
                else:  # flat
                    cancellation_fee_applied = platform_setting.fee_value

                DriverWalletTransaction.objects.create(
                    driver=request.user,
                    ride=ride,
                    amount=-cancellation_fee_applied,
                    transaction_type="penalty",
                    description=f"Ride cancellation fee for ride {ride.id}"
                )
                # Reset free cancellations
                driver.driver_cancellations_left = 2
                driver.save()
                print(f"🔄 Driver {driver.id} cancellations reset to 2 after fee.")
            except PlatformSetting.DoesNotExist:
                print("⚠️ No active cancellation fee setting found")

        # Mark ride cancelled
        ride.status = "cancelled"
        ride.save()
        print(f"⚠️ Ride {ride.id} cancelled by driver {request.user.id}")

        # Send WebSocket notification to rider
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'ride_cancellation_{ride.id}',
                {
                    'type': 'ride_cancellation_message',
                    'message': {
                        'ride_id': str(ride.id),
                        'status': 'cancelled',
                        'cancelled_by': 'driver',
                        'driver_id': str(request.user.id),
                        'driver_name': request.user.username,
                        'cancellation_fee_applied': str(cancellation_fee_applied),
                        'message': f"Your ride has been cancelled by driver {request.user.username}.",
                        'timestamp': ride.created_at.isoformat()
                    }
                }
            )
            print(f"✅ WebSocket message sent to rider {ride.user.id}")
        except Exception as e:
            print("❌ WebSocket error:", e)

        # FCM notification
        try:
            if ride.user:
                send_fcm_notification(
                    user=ride.user,
                    title="Ride Cancelled ❌",
                    body=f"Your ride has been cancelled by {request.user.username}.",
                    data={
                        "ride_id": str(ride.id),
                        "status": "cancelled",
                        "cancelled_by": "driver",
                        "driver_id": str(request.user.id),
                        "driver_name": request.user.username,
                        "cancellation_fee_applied": str(cancellation_fee_applied),
                    }
                )
                print(f"✅ FCM sent to rider {ride.user.id}")
        except Exception as e:
            print("❌ FCM error:", e)

        return Response({
            "message": "Ride cancelled successfully.",
            "cancellation_fee_applied": str(cancellation_fee_applied),
        }, status=200)
    

class RideDetailAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related('user').prefetch_related('ride_stops').get(
                id=ride_id, 
                status='accepted',
                driver=request.user  # ensures only assigned driver can view
            )
        except RideRequest.DoesNotExist:
            return Response({'detail': 'Ride not found or not yet accepted or completed'}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Count cancelled rides by this driver
        cancelled_count = RideRequest.objects.filter(
            driver=request.user,
            status="cancelled"
        ).count()

        serializer = RideDetailSerializer(ride, context={'request': request})

        # ✅ Add cancelled_count to response
        response_data = serializer.data
        response_data['cancelled_rides_count'] = cancelled_count

        return Response(response_data, status=status.HTTP_200_OK)



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
class SetRideStartTimeAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Only driver of the ride can start it
        if ride.driver != request.user:
            return Response({"detail": "You are not allowed to start this ride."}, status=403)

        # ✅ Check if OTP exists and is verified
        try:
            otp = ride.otp  # related_name='otp'
            if not otp.is_verified:
                return Response({"detail": "OTP has not been verified. Ride cannot start."},
                                status=status.HTTP_403_FORBIDDEN)
        except RideOTP.DoesNotExist:
            return Response({"detail": "OTP verification is required before starting the ride."},
                            status=status.HTTP_403_FORBIDDEN)

        # ✅ Prevent starting twice
        if ride.start_time:
            return Response({"detail": "Start time already set."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Capture IST start time
        current_time = timezone.now()
        ride.start_time = current_time
        ride.status = "accepted"  # still ongoing
        ride.save()

        expiry = current_time + timedelta(hours=12)
        session = RideLocationSession.objects.create(
            ride=ride,
            expiry_time=expiry
        )
        ist_time = current_time.astimezone(pytz.timezone("Asia/Kolkata"))

        # 🔔 Send FCM notification to rider
        try:
            from notifications.fcm import send_fcm_notification

            send_fcm_notification(
                user=ride.user,
                title="Ride Started 🚖",
                body=f"Your ride with {request.user.username} has started.",
                data={
                    "ride_id": str(ride.id),
                    "status": "started",
                    "driver_id": str(request.user.id),
                    "driver_name": request.user.username,
                    "start_time": ist_time.strftime('%Y-%m-%d %I:%M %p'),
                }
            )
            print("✅ FCM notification sent to rider.")
        except Exception as e:
            print("❌ Error sending FCM notification:", e)

        return Response({
            "ride_id": ride.id,
            "start_time": current_time,
            "start_time_ist": ist_time.strftime('%Y-%m-%d %I:%M %p'),
            "session_id": str(session.session_id),
            "expiry_time": session.expiry_time,
        }, status=status.HTTP_200_OK)

class SetRideEndTimeAPIView(StandardResponseMixin, APIView):
    def post(self, request, ride_id):
        try:
            ride = RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        if ride.end_time:
            return Response({"detail": "End time already set."}, status=status.HTTP_400_BAD_REQUEST)

        ride.end_time = timezone.now()
        ride.save()

        # Convert to IST for response
        ist_time = ride.end_time.astimezone(pytz.timezone("Asia/Kolkata"))

        # --- ✅ WebSocket notification (keep existing) ---
        channel_layer = get_channel_layer()
        group_name = f"ride_{ride.id}"  # must match consumer's group naming

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "ride.completed",
                "ride_id": ride.id,
                "message": "Your ride has been completed.",
                "end_time": ist_time.strftime('%Y-%m-%d %I:%M %p')
            }
        )

        # --- ✅ FCM Notifications ---
        from notifications.fcm import send_fcm_notification  # import your helper

        try:
            # Notify Rider
            send_fcm_notification(
                user=ride.user,
                title="Ride Completed 🎉",
                body=f"Your ride ending at {ist_time.strftime('%I:%M %p')} has been completed.",
                data={
                    "ride_id": str(ride.id),
                    "type": "ride_completed",
                    "end_time": ist_time.strftime('%Y-%m-%d %I:%M %p')
                }
            )

            # Notify Driver
            if ride.driver:
                send_fcm_notification(
                    user=ride.driver,
                    title="Ride Completed ✅",
                    body=f"You successfully completed the ride at {ist_time.strftime('%I:%M %p')}.",
                    data={
                        "ride_id": str(ride.id),
                        "type": "ride_completed",
                        "end_time": ist_time.strftime('%Y-%m-%d %I:%M %p')
                    }
                )
        except Exception as e:
            print(f"❌ Failed to send FCM notifications for ride {ride.id} | error={e}")

        return Response({
            "ride_id": ride.id,
            "end_time_utc": ride.end_time,
            "end_time_ist": ist_time.strftime('%Y-%m-%d %I:%M %p')
        }, status=status.HTTP_200_OK)


# public ride location
class EmergencyShareAPIView(APIView):
    permission_classes = []  # Public

    def get(self, request, session_id):
        try:
            session = RideLocationSession.objects.get(session_id=session_id)
        except RideLocationSession.DoesNotExist:
            return Response({"detail": "Invalid link"}, status=status.HTTP_404_NOT_FOUND)

        if session.is_expired():
            return Response({"detail": "Link expired"}, status=status.HTTP_403_FORBIDDEN)

        latest_update = session.updates.order_by("-recorded_at").first()
        if not latest_update:
            return Response({"detail": "No location yet"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "latitude": latest_update.latitude,
            "longitude": latest_update.longitude,
            "updated_at": latest_update.recorded_at
        })



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
    
    
class VerifyRideOTPView(APIView):
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

        # Mark OTP as verified and update ride status
        otp_obj.is_verified = True
        otp_obj.save()
        ride.status = 'accepted'
        ride.save()

        # WebSocket notification to rider
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"rider_otp_{ride.user.id}",
            {
                "type": "otp_verified",
                "message": f"Your ride {ride.id} has been verified and accepted by the driver.",
                "ride_id": ride.id
            }
        )

        return Response({"message": "OTP verified"}, status=200)
    
    
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

        # Base ride price (before GST)
        ride_price = ride.offered_price if ride.offered_price else ride.estimated_price

        # Apply GST if configured
        gst_percentage = 0
        ride_price_with_gst = None
        gst_setting = PlatformSetting.objects.filter(fee_reason="GST", is_active=True).first()
        if gst_setting:
            gst_percentage = float(gst_setting.fee_value)
            ride_price_with_gst = round(float(ride_price) * (1 + gst_percentage / 100), 2) if ride_price else None

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
                "gst_percentage": gst_percentage,
                "grand_total_with_gst": ride_price_with_gst
            }
        except RidePaymentDetail.DoesNotExist:
            # fallback minimal payment info
            payment_info = {
                "grand_total": float(ride_price) if ride_price else None,
                "gst_percentage": gst_percentage,
                "grand_total_with_gst": ride_price_with_gst,
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
                "price": float(ride_price) if ride_price else None,
                "price_with_gst": ride_price_with_gst,
                "gst_percentage": gst_percentage
            },
            "payment_summary": payment_info
        }, status=status.HTTP_200_OK)


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
                active_fee = PlatformSetting.objects.filter(fee_reason="Platform Fees", is_active=True).first()
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

        # ✅ WebSocket notification to user (for all payment types)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'payment_normal_ride_{ride.id}',
            {
                'type': 'payment_status_update',
                'payment_status': payment_status,
                'message': f"Driver acknowledged payment for Ride #{ride.id}.",
            }
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

class DriverRideEarningDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideRequest.objects.select_related("user").get(
                id=ride_id, driver=request.user, status="completed"
            )
        except RideRequest.DoesNotExist:
            return Response(
                {"detail": "Ride not found or not completed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = RidePaymentDetail.objects.get(ride=ride)
        except RidePaymentDetail.DoesNotExist:
            return Response(
                {"detail": "Payment details not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Duration
        duration = None
        if ride.start_time and ride.end_time:
            duration = ride.end_time - ride.start_time

        ist = pytz.timezone("Asia/Kolkata")
        start_time_ist = (
            ride.start_time.astimezone(ist).strftime("%Y-%m-%d %I:%M %p")
            if ride.start_time
            else None
        )
        end_time_ist = (
            ride.end_time.astimezone(ist).strftime("%Y-%m-%d %I:%M %p")
            if ride.end_time
            else None
        )

        # Rider rating
        rating_data = None
        try:
            rating = DriverRating.objects.get(ride_request=ride, driver=request.user)
            rating_data = {"rating": float(rating.rating), "review": rating.review}
        except DriverRating.DoesNotExist:
            rating_data = None

        # ---------------- CASH PAYMENT ----------------
        if payment.payment_method == "cash":
            ride_price = ride.offered_price or ride.estimated_price
            tip_amount = payment.tip_amount or 0

            # Cash rides → platform fee deferred
            platform_fee = PlatformSetting.objects.filter(fee_reason="platform fees", is_active=True).first()
            fee_value = fee_type = None
            fee_amount = Decimal(0)
            if platform_fee:
                fee_type = platform_fee.fee_type
                fee_value = platform_fee.fee_value
                if fee_type == "percentage":
                    fee_amount = (ride_price * fee_value) / 100
                else:
                    fee_amount = fee_value

            payment_info = {
                "payment_method": "cash",
                "ride_price": float(ride_price) if ride_price else None,
                "tip_amount": float(tip_amount),
                "platform_fee_type": fee_type,
                "platform_fee_value": float(fee_value) if fee_value else None,
                "platform_fee_pending": float(fee_amount),
                "total_received_in_cash": float(ride_price + tip_amount)
                if ride_price
                else None,
                "note": "Cash collected directly. Platform fee pending settlement.",
            }

        # ---------------- UPI / WALLET ----------------
        else:
            platform_fee = PlatformSetting.objects.filter(fee_reason="platform fees", is_active=True).first()

            fee_amount = Decimal(0)
            fee_type = fee_value = None
            if platform_fee:
                fee_type = platform_fee.fee_type
                fee_value = platform_fee.fee_value
                if fee_type == "percentage":
                    fee_amount = (payment.driver_earnings * fee_value) / 100
                else:
                    fee_amount = fee_value

            total_received = (
                payment.driver_earnings - fee_amount + payment.tip_amount
            )
            payment_info = {
                "payment_method": payment.payment_method,
                "driver_earnings": float(payment.driver_earnings),
                "tip_amount": float(payment.tip_amount),
                "platform_fee_type": fee_type,
                "platform_fee_value": float(fee_value) if fee_value else None,
                "platform_fee_deducted": float(fee_amount),
                "total_received_by_driver": float(total_received),
            }

        return Response(
            {
                "rider": {
                    "id": ride.user.id,
                    "username": ride.user.username,
                    "email": ride.user.email,
                    "profile_image": request.build_absolute_uri(
                        ride.user.profile.url
                    )
                    if ride.user.profile
                    else None,
                },
                "ride_info": {
                    "distance_km": float(ride.distance_km),
                    "start_time": start_time_ist,
                    "end_time": end_time_ist,
                    "duration": str(duration) if duration else None,
                },
                "payment_summary": payment_info,
                "rider_rating": rating_data,
            },
            status=status.HTTP_200_OK,
        )


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

        # ---------- Helpers ----------
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
            # Only include earnings, exclude withdrawals and cash payments
            return DriverWalletTransaction.objects.filter(
                driver=user,
                created_at__range=(start, end),
                transaction_type="ride_earning"  # Only include earnings
            ).aggregate(total=Sum('amount'))['total'] or 0.0

        # ---------- Available balance (withdrawable) ----------
        # Calculate available balance (excluding cash payments but including all transaction types)
        available_balance = DriverWalletTransaction.objects.filter(
            driver=user
        ).exclude(
            # Exclude cash payment transactions
            description__icontains="Cash payment for Ride"
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        # ---------- Cash vs UPI totals ----------
        cash_total_qs = RidePaymentDetail.objects.filter(
            ride__driver=user,
            payment_method="cash",
            payment_status="completed"
        ).annotate(
            total_with_tips=ExpressionWrapper(
                F("driver_earnings") + F("tip_amount"),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        cash_total = cash_total_qs.aggregate(total=Sum("total_with_tips"))["total"] or 0.0
        
        upi_total = RidePaymentDetail.objects.filter(
            ride__driver=user,
            payment_method="upi",
            payment_status="completed"
        ).aggregate(total=Sum("driver_earnings"))["total"] or 0.0

        # UPI grand total = sum of all UPI payouts ever credited (only earnings)
        upi_grand_total = DriverWalletTransaction.objects.filter(
            driver=user,
            transaction_type="ride_earning",  # Only include earnings
            ride__payment_detail__payment_method="upi"
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        # ---------- Pending platform fees ----------
        pending_platform_fees = DriverPendingFee.objects.filter(
            driver=user,
            settled=False
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        # ---------- Additional metrics for better insights ----------
        # Total earnings (excluding withdrawals and cash payments)
        total_earnings = DriverWalletTransaction.objects.filter(
            driver=user,
            transaction_type="ride_earning"  # Only include earnings
        ).exclude(
            description__icontains="Cash payment for Ride"
        ).aggregate(total=Sum('amount'))['total'] or 0.0


        # ---------- Final summary ----------
        summary = {
            "today_earnings": float(get_earning(start_today, end_today)),
            "yesterday_earnings": float(get_earning(start_yesterday, end_yesterday)),
            "this_week_earnings": float(get_earning(start_of_week, now)),
            "this_month_earnings": float(get_earning(start_of_month, now)),
            
            "cash_total": float(cash_total),
            "upi_total": float(upi_total),
            "upi_grand_total": float(upi_grand_total),
            "available_balance": float(available_balance),
            
            # Additional metrics for better understanding
            "total_earnings": float(total_earnings),
           
            
            "pending_platform_fees": float(pending_platform_fees),
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

        profile_url = (
            request.build_absolute_uri(user.profile.url)
            if user.profile and hasattr(user.profile, 'url') else None
        )

        return Response({
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "profile_image": profile_url,
            "vehicle_info": {
                "id":          vehicle_info.id if vehicle_info else None,
                "vehicle_number": vehicle_info.vehicle_number if vehicle_info else None,
                "car_name":       f"{vehicle_info.car_company} {vehicle_info.car_model}" if vehicle_info else None,
            }
        }, status=200)

    def put(self, request):
        user = request.user

        if user.role != 'driver':
            return Response({"detail": "Access denied. Only drivers allowed."}, status=403)

        # Only allow username, email and profile_image to be updated:
        username       = request.data.get('username')
        email          = request.data.get('email')
        profile_image  = request.FILES.get('profile_image')

        if username:
            user.username = username

        if email:
            user.email = email

        if profile_image:
            user.profile = profile_image

        user.save()

        # For response
        vehicle_info = getattr(user, 'vehicle_info', None)
        profile_url = (
            request.build_absolute_uri(user.profile.url)
            if user.profile and hasattr(user.profile, 'url') else None
        )

        return Response({
            "message": "Profile updated successfully",
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,       # <-- returned as read-only
            "profile_image": profile_url,
            "vehicle_info": {
                "id":          vehicle_info.id if vehicle_info else None,
                "vehicle_number": vehicle_info.vehicle_number if vehicle_info else None,
                "car_name":       f"{vehicle_info.car_company} {vehicle_info.car_model}" if vehicle_info else None,
            }
        }, status=200)

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

        # Check if driver has any pending or unprocessed cashout requests
        pending_requests = CashOutRequest.objects.filter(
            driver=user,
            status__in=['pending']  # Add other statuses if needed, like 'processing'
        ).exists()
        
        if pending_requests:
            return Response({"error": "You already have a pending cashout request. Please wait until it is processed."}, status=400)

        # ✅ Calculate available balance (excluding cash payments) - consistent with DriverEarningsSummaryAPIView
        available_balance = DriverWalletTransaction.objects.filter(
            driver=user
        ).exclude(
            # Exclude cash payment transactions
            description__icontains="Cash payment for Ride"
        ).aggregate(total=Sum('amount'))['total'] or 0.0

        if amount > available_balance:
            return Response({"error": "Withdrawal amount exceeds available balance."}, status=400)

        # ✅ Create cash-out request record (only pending, no deduction yet)
        CashOutRequest.objects.create(driver=user, amount=amount)

        return Response({"message": "Cash out request submitted. Awaiting approval."}, status=201)

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
        ).select_related('otp', 'user')  # also load user for fewer queries

        serializer = ActiveRideWithRiderSerializer(rides, many=True, context={'request': request})
        return Response(serializer.data)
