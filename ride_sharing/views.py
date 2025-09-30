from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from .tasks import calculate_segments_and_eta
from .mixins import StandardResponseMixin
from django.db import IntegrityError, transaction
from rider_part.models import DriverWalletTransaction
from admin_part.models import PlatformSetting
from django.db.models import Sum
from django.db import transaction
from rider_part.models import DriverPendingFee
import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from datetime import datetime, time
from rest_framework.response import Response
from auth_api.models import CustomUser,DriverVehicleInfo
from rest_framework import status
from auth_api.models import DriverRating
from . models import *
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from decimal import Decimal
from pytz import timezone as pytz_timezone
from django.utils import timezone
from decimal import Decimal
from .utils.google_maps import get_route_segments_with_distance
from django.db.models import Q,Avg,Prefetch
from django.shortcuts import get_object_or_404
from datetime import date


class AddRideShareVehicleAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RideShareVehicleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return self.response(serializer.data, 201)
        return self.response(serializer.errors, 400)
 

class GetRideShareVehicleAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        vehicles = RideShareVehicle.objects.filter(owner=user)

        serializer = RideShareVehicleSerializer(vehicles, many=True, context={'request': request})
        return self.response(data=serializer.data, status_code=200)
    
class CreateRideShareCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data.copy()
        stops_data = data.pop('stops', [])
        
        with transaction.atomic():
            # Handle vehicle logic
            if user.role == 'driver':
                try:
                    vehicle_info = DriverVehicleInfo.objects.get(user=user)
                except DriverVehicleInfo.DoesNotExist:
                    return Response({"error": "Driver vehicle info not found."}, status=status.HTTP_404_NOT_FOUND)

                data['vehicle_number'] = vehicle_info.vehicle_number
                data['model_name'] = vehicle_info.car_model
                data['seat_capacity'] = 4
            else:
                vehicle_id = data.get('vehicle')
                if not vehicle_id:
                    return Response({"error": "Vehicle ID is required for rider."}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    vehicle = RideShareVehicle.objects.get(id=vehicle_id, owner=user)
                except RideShareVehicle.DoesNotExist:
                    return Response({"error": "Vehicle not found or access denied."}, status=status.HTTP_404_NOT_FOUND)
                if not vehicle.approved:
                    return Response({"error": "Vehicle is not approved yet."}, status=status.HTTP_400_BAD_REQUEST)

                data['vehicle'] = vehicle.id
                data['vehicle_number'] = vehicle.vehicle_number
                data['model_name'] = vehicle.model_name
                data['seat_capacity'] = vehicle.seat_capacity

            # Create the ride
            booking_serializer = RideShareBookingCreateSerializer(data=data, context={'request': request})
            booking_serializer.is_valid(raise_exception=True)
            booking = booking_serializer.save()

            # Add stops
            for stop_data in stops_data:
                stop_serializer = RideShareStopCreateSerializer(data=stop_data)
                stop_serializer.is_valid(raise_exception=True)
                stop_serializer.save(ride_booking=booking)

            # Trigger Celery task
            calculate_segments_and_eta.delay(booking.id)

            return Response({
                "booking_id": booking.id,
                "message": "Ride and stops created successfully. Route will be processed."
            }, status=status.HTTP_201_CREATED)


class EstimateBookingPriceAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        try:
            booking = RideShareBooking.objects.get(id=booking_id, user=request.user)
        except RideShareBooking.DoesNotExist:
            return self.response({'error': 'Booking not found or access denied.'}, status_code=404)

        if not booking.distance_km:
            return self.response({'error': 'Distance not set for this booking.'}, status_code=400)

        price_setting = RideSharePriceSetting.objects.first()
        if not price_setting:
            return self.response({'error': 'Ride price settings not configured.'}, status_code=500)

        min_price = price_setting.min_price_per_km * booking.distance_km
        max_price = price_setting.max_price_per_km * booking.distance_km

        return self.response({
            'booking_id': booking.id,
            'from': booking.from_location,
            'to': booking.to_location,
            'distance_km': float(booking.distance_km),
            'estimated_min_price': float(min_price),
            'estimated_max_price': float(max_price)
        })
    

class RideSegmentListAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            booking = RideShareBooking.objects.get(id=ride_id, user=request.user)
        except RideShareBooking.DoesNotExist:
            return self.response({'error': 'Ride booking not found or access denied.'}, status_code=404)

        segments = RideShareRouteSegment.objects.filter(ride_booking=booking)
        serializer = RideShareRouteSegmentSerializer(segments, many=True)
        return self.response(serializer.data)


class BulkUpdateRideSegmentPricesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, ride_id):
        booking = get_object_or_404(RideShareBooking, id=ride_id, user=request.user)

        serializer = RideShareRouteSegmentBulkPriceUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.response(serializer.errors, status_code=400)

        updated = 0
        not_found_ids = []

        for seg_data in serializer.validated_data['segments']:
            segment = RideShareRouteSegment.objects.filter(
                ride_booking=booking,
                id=seg_data['id']
            ).first()

            if segment:
                segment.price = seg_data['price']
                segment.save()
                updated += 1
            else:
                not_found_ids.append(seg_data['id'])

        return self.response({
            "message": f"{updated} segment(s) updated.",
            "not_found_ids": not_found_ids
        }, status_code=200)
    
class RidePriceUpdateAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, ride_id):
        ride = get_object_or_404(RideShareBooking, id=ride_id, user=request.user)

        # Allow price update only if ride is still in draft
        if ride.status != 'draft':
            return self.response({
                "error": "Only draft rides can have their price updated."
            }, status_code=HTTP_400_BAD_REQUEST)

        serializer = RidePriceUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.response(serializer.errors, status_code=HTTP_400_BAD_REQUEST)

        # Update price and change status to published
        ride.price = serializer.validated_data['price']
        ride.status = 'published'
        ride.save()

        return self.response({
            "message": "Ride price updated and ride published successfully.",
            "ride_id": ride.id,
            "updated_price": ride.price,
            "new_status": ride.status
        }, status_code=HTTP_200_OK)

    
    
class UserPublishedRidesAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rides = RideShareBooking.objects.filter(user=request.user, status='published').order_by('-ride_date', '-ride_time')
        serializer = RideShareBookingSerializer(rides, many=True)
        return self.response(serializer.data)
    
class RideStopSegmentListAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        booking = get_object_or_404(RideShareBooking, id=ride_id, user=request.user)

        stops = RideShareStop.objects.filter(ride_booking=booking).order_by('order')
        segments = RideShareRouteSegment.objects.filter(ride_booking=booking)
        join_requests = RideJoinRequest.objects.filter(ride=booking)

        stop_data = RideShareStopSerializer(stops, many=True).data
        segment_data = RideShareSegmentPriceSerializer(segments, many=True).data
        join_request_data = RideJoinRequestSerializer(join_requests, many=True, context={'request': request}).data


        return self.response({
            "stops": stop_data,
            "segments": segment_data,
            "join_requests": join_request_data
        })

class RideShareSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from_location = request.query_params.get('from')
        to_location = request.query_params.get('to')
        date = request.query_params.get('date')
        time_str = request.query_params.get('time')
        seats_required = int(request.query_params.get('seats', 1))

        if not from_location or not to_location:
            return Response({
                "status": False,
                "message": "Both 'from' and 'to' locations are required."
            }, status=status.HTTP_400_BAD_REQUEST)
        ride_time_obj = None
        if time_str:
            try:
                ride_time_obj = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                return Response({
                    "status": False,
                    "message": "Invalid time format. Use HH:MM (e.g., 08:30)."
                }, status=status.HTTP_400_BAD_REQUEST)
        booking_filters = (
            Q(status="published") &
            Q(seats_remaining__gte=seats_required) &
            ~Q(user=request.user)
        )
        if date:
            booking_filters &= Q(ride_date=date)
        if ride_time_obj:
            booking_filters &= Q(ride_time__gte=ride_time_obj)

        response_data = []

        # Prefetch related data to optimize queries
        prefetch_stops = Prefetch('stops', queryset=RideShareStop.objects.all())
        prefetch_segments = Prefetch('route_segments', queryset=RideShareRouteSegment.objects.all())
        prefetch_join_requests = Prefetch(
            'join_requests', 
            queryset=RideJoinRequest.objects.filter(status='accepted').select_related('user')
        )

        # --- 1. Direct Rides ---
        direct_rides = RideShareBooking.objects.filter(
            booking_filters &
            Q(from_location__icontains=from_location) &
            Q(to_location__icontains=to_location)
        ).select_related('user').prefetch_related(
            prefetch_stops,
            prefetch_segments,
            prefetch_join_requests
        )

        for ride in direct_rides:
            # Calculate average rating based on user role
            if ride.user.role == 'rider':
                avg_rating = RiderRating.objects.filter(
                    rider=ride.user
                ).aggregate(avg_rating=Avg('rating'))['avg_rating']
            else:  # driver
                avg_rating = DriverRating.objects.filter(
                    driver=ride.user
                ).aggregate(avg_rating=Avg('rating'))['avg_rating']
            
            # Get accepted join requests
            accepted_requests = ride.join_requests.all()
            
            # Get profile images of joined users
            joined_users_profiles = [
                request.build_absolute_uri(req.user.profile.url) 
                for req in accepted_requests 
                if req.user.profile
            ]
            
            response_data.append({
                "ride_id": ride.id,
                "ride_date": ride.ride_date.strftime('%Y-%m-%d'),
                "segment_from": ride.from_location,
                "segment_to": ride.to_location,
                "segment_distance_km": str(ride.distance_km),
                "segment_price": int(round(ride.price)) if ride.price else None,
                "from_arrival_time": ride.ride_time.strftime('%H:%M:%S'),
                "to_arrival_time": ride.to_location_estimated_arrival_time.strftime('%H:%M:%S') if ride.to_location_estimated_arrival_time else None,
                "user_name": ride.user.username,
                "user_profile": request.build_absolute_uri(ride.user.profile.url) if ride.user.profile else None,
                "user_role": ride.user.role,
                "avg_rating": round(avg_rating, 1) if avg_rating is not None else None,
                "available_seats": ride.seats_remaining,
                "joined_users_count": accepted_requests.count(),
                "joined_users_profiles": joined_users_profiles,
                "segment_id": None  # Explicitly show None for direct rides
            })

        # --- 2. Segment-Based Rides ---
        segment_qs = RideShareRouteSegment.objects.filter(
            Q(from_stop__icontains=from_location) & Q(to_stop__icontains=to_location)
        ).select_related('ride_booking')
        segment_ride_ids = segment_qs.values_list('ride_booking_id', flat=True)

        segment_rides = RideShareBooking.objects.filter(
            booking_filters & Q(id__in=segment_ride_ids)
        ).select_related('user').prefetch_related(
            prefetch_stops,
            prefetch_segments,
            prefetch_join_requests
        )

        for ride in segment_rides:
            # Skip if already included as a direct ride
            if any(r["ride_id"] == ride.id and r["segment_from"].lower() == from_location.lower() and r["segment_to"].lower() == to_location.lower() for r in response_data):
                continue

            matching_segment = segment_qs.filter(ride_booking=ride).first()
            if not matching_segment:
                continue

            # Get from_arrival_time
            if matching_segment.from_stop.lower() == ride.from_location.lower():
                from_arrival_time = ride.ride_time.strftime('%H:%M:%S')
            else:
                from_stop_obj = RideShareStop.objects.filter(
                    ride_booking=ride, stop_location__icontains=matching_segment.from_stop
                ).first()
                from_arrival_time = (
                    from_stop_obj.estimated_arrival_time.strftime('%H:%M:%S')
                    if from_stop_obj and from_stop_obj.estimated_arrival_time else None
                )

            # Get to_arrival_time
            to_stop_obj = RideShareStop.objects.filter(
                ride_booking=ride, stop_location__icontains=matching_segment.to_stop
            ).first()
            to_arrival_time = (
                to_stop_obj.estimated_arrival_time.strftime('%H:%M:%S')
                if to_stop_obj and to_stop_obj.estimated_arrival_time else None
            )

            # Calculate average rating based on user role
            if ride.user.role == 'rider':
                avg_rating = RiderRating.objects.filter(
                    rider=ride.user
                ).aggregate(avg_rating=Avg('rating'))['avg_rating']
            else:  # driver
                avg_rating = DriverRating.objects.filter(
                    driver=ride.user
                ).aggregate(avg_rating=Avg('rating'))['avg_rating']
            
            # Get accepted join requests
            accepted_requests = ride.join_requests.all()
            
            # Get profile images of joined users
            joined_users_profiles = [
                request.build_absolute_uri(req.user.profile.url) 
                for req in accepted_requests 
                if req.user.profile
            ]

            response_data.append({
                "ride_id": ride.id,
                "ride_date": ride.ride_date.strftime('%Y-%m-%d'),
                "segment_from": matching_segment.from_stop,
                "segment_to": matching_segment.to_stop,
                "segment_distance_km": str(matching_segment.distance_km),
                "segment_price": int(round(matching_segment.price)),
                "from_arrival_time": from_arrival_time,
                "to_arrival_time": to_arrival_time,
                "user_name": ride.user.username,
                "user_profile": request.build_absolute_uri(ride.user.profile.url) if ride.user.profile else None,
                "user_role": ride.user.role,
                "avg_rating": round(float(avg_rating), 1) if avg_rating else None,
                "available_seats": ride.seats_remaining,
                "joined_users_count": accepted_requests.count(),
                "joined_users_profiles": joined_users_profiles,
                "segment_id": matching_segment.id  # Include segment ID
            })

        return Response({
            "status": True,
            "message": "Rides found." if response_data else "No rides found.",
            "data": response_data
        }, status=status.HTTP_200_OK)


class RideJoinRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        ride_id = request.data.get('ride_id')
        segment_id = request.data.get('segment_id')  # Optional
        seats_requested = int(request.data.get('seats_requested', 1))
       

        if not ride_id:
            return Response({"status": False, "message": "ride_id is required."}, status=400)

        ride = get_object_or_404(RideShareBooking, id=ride_id)

        # If segment is provided, validate it
        segment = None
        if segment_id:
            segment = get_object_or_404(RideShareRouteSegment, id=segment_id, ride_booking=ride)

        # Check for duplicate join request
        existing_request = RideJoinRequest.objects.filter(
            ride=ride, user=user, segment=segment
        ).exists()

        if existing_request:
            return Response({"status": False, "message": "You have already requested to join this ride."}, status=400)

        # Check seat availability
        if ride.seats_remaining is not None and ride.seats_remaining < seats_requested:
            return Response({"status": False, "message": "Not enough seats available."}, status=400)

        # Create join request
        join_request = RideJoinRequest.objects.create(
            ride=ride,
            user=user,
            segment=segment,
            seats_requested=seats_requested,
        )

        return Response({
            "status": True,
            "message": "Join request submitted successfully.",
            "data": {
                "ride_id": ride.id,
                "segment_id": segment.id if segment else None,
                "seats_requested": join_request.seats_requested,
                "status": join_request.status,
                "created_at": join_request.created_at
            }
        }, status=201)
    
class RideJoinRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, join_request_id):
        try:
            join_request = (
                RideJoinRequest.objects
                .select_related('user', 'segment', 'ride')
                .get(id=join_request_id, ride__user=request.user)
            )
        except RideJoinRequest.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Join request not found or access denied.'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = RideJoinRequestViewSerializer(
            join_request,
            context={'request': request, 'ride': join_request.ride}
        )

        return Response({
            'status': True,
            'message': 'Join request found.',
            'data': serializer.data
        })

    
class AcceptRideJoinRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_request_id):
        try:
            ride_request = RideJoinRequest.objects.select_related('ride').get(id=ride_request_id)
        except RideJoinRequest.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Ride join request not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Ensure the logged-in user is the owner of the ride
        if ride_request.ride.user != request.user:
            return Response({
                'status': False,
                'message': 'You are not authorized to accept this request.'
            }, status=status.HTTP_403_FORBIDDEN)

        # Prevent duplicate acceptance
        if ride_request.status == 'accepted':
            return Response({
                'status': False,
                'message': 'Request already accepted.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if enough seats are available
        if ride_request.ride.seats_remaining is not None and ride_request.seats_requested > ride_request.ride.seats_remaining:
            return Response({
                'status': False,
                'message': 'Not enough seats available.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update ride request status
        ride_request.status = 'accepted'
        ride_request.save()

        # Deduct seats from the ride
        ride = ride_request.ride
        if ride.seats_remaining is not None:
            ride.seats_remaining -= ride_request.seats_requested
            ride.save()

        return Response({
            'status': True,
            'message': 'Ride join request accepted successfully.'
        })
    

class CancelJoinRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, join_request_id):
        try:
            join_request = RideJoinRequest.objects.get(id=join_request_id)
        except RideJoinRequest.DoesNotExist:
            return Response({'error': 'Join request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if join_request.user != request.user:
            return Response({'error': 'You are not authorized to cancel this join request.'}, status=status.HTTP_403_FORBIDDEN)

        if join_request.status in ['cancelled', 'rejected']:
            return Response({'error': f'Join request is already {join_request.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        join_request.status = 'cancelled'
        join_request.save()

        return Response({'message': 'Join request cancelled successfully.'}, status=status.HTTP_200_OK)


class MyRideJoinRequestsAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        join_requests = RideJoinRequest.objects.filter(user=request.user).order_by('-created_at')
        serializer = RideJoinRequestDetailSerializer(join_requests, many=True, context={"request": request})
        return self.response(serializer.data)
    
class AcceptedJoinRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideShareBooking.objects.prefetch_related('stops').get(id=ride_id)
        except RideShareBooking.DoesNotExist:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        accepted_requests = RideJoinRequest.objects.filter(
            ride=ride, status='accepted'
        ).select_related('user', 'segment')

        serializer = AcceptedJoinRequestSerializer(accepted_requests, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideShareBooking.objects.get(id=ride_id)
        except RideShareBooking.DoesNotExist:
            return Response({"detail": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the current user is the creator of the ride
        if ride.user != request.user:
            return Response({"detail": "You are not authorized to cancel this ride."}, status=status.HTTP_403_FORBIDDEN)

        if ride.status == 'cancelled':
            return Response({"detail": "This ride is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        # Update status
        ride.status = 'cancelled'
        ride.save()

        return Response({"detail": "Ride has been successfully cancelled."}, status=status.HTTP_200_OK)
    

class RideDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_duration_format(self, total_minutes):
        hours = int(total_minutes // 60)
        minutes = int(total_minutes % 60)
        return {
            'hours': hours,
            'minutes': minutes,
            'display': f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        }

    def get(self, request):
        ride_id = request.query_params.get('ride_id')
        segment_id = request.query_params.get('segment_id')

        if not ride_id:
            return Response({
                "status": False,
                "message": "ride_id is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride = RideShareBooking.objects.select_related(
                'user', 'vehicle'
            ).prefetch_related(
                'route_segments', 'stops'
            ).get(id=ride_id)
        except RideShareBooking.DoesNotExist:
            return Response({
                "status": False,
                "message": "Ride not found."
            }, status=status.HTTP_404_NOT_FOUND)

        response_data = {
            "ride_date": ride.ride_date.strftime('%Y-%m-%d'),
            "passenger_notes": ride.passenger_notes,
            "passenger_notes": ride.passenger_notes,
            "ride_creator": {},
            "ride_details": {
                "duration": None,
                "start_time": None,
                "end_time": None
            },
            "coordinates": {}
        }

        start_time, end_time = None, None

        if segment_id:
            try:
                segment = RideShareRouteSegment.objects.get(id=segment_id, ride_booking=ride)

                response_data["ride_details"].update({
                    "from_location": segment.from_stop,
                    "to_location": segment.to_stop,
                    "distance_km": float(segment.distance_km),
                    "price": float(segment.price),
                    "total_price": float(segment.price)
                })

                if segment.from_stop.lower() == ride.from_location.lower():
                    response_data["coordinates"].update({
                        "from_lat": ride.from_location_lat,
                        "from_lng": ride.from_location_lng
                    })
                    start_time = ride.ride_time
                else:
                    from_stop = RideShareStop.objects.filter(
                        ride_booking=ride,
                        stop_location__icontains=segment.from_stop
                    ).first()
                    if from_stop:
                        response_data["coordinates"].update({
                            "from_lat": from_stop.stop_lat,
                            "from_lng": from_stop.stop_lng
                        })
                        start_time = from_stop.estimated_arrival_time

                if segment.to_stop.lower() == ride.to_location.lower():
                    response_data["coordinates"].update({
                        "to_lat": ride.to_location_lat,
                        "to_lng": ride.to_location_lng
                    })
                    end_time = ride.to_location_estimated_arrival_time
                else:
                    to_stop = RideShareStop.objects.filter(
                        ride_booking=ride,
                        stop_location__icontains=segment.to_stop
                    ).first()
                    if to_stop:
                        response_data["coordinates"].update({
                            "to_lat": to_stop.stop_lat,
                            "to_lng": to_stop.stop_lng
                        })
                        end_time = to_stop.estimated_arrival_time

            except RideShareRouteSegment.DoesNotExist:
                return Response({
                    "status": False,
                    "message": "Segment not found for this ride."
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            ride_price = float(ride.price) if ride.price is not None else 0.0
            response_data["ride_details"].update({
                "from_location": ride.from_location,
                "to_location": ride.to_location,
                "distance_km": float(ride.distance_km) if ride.distance_km is not None else None,
                "price": ride_price,
                "total_price": ride_price,
                
            })

            response_data["coordinates"].update({
                "from_lat": ride.from_location_lat,
                "from_lng": ride.from_location_lng,
                "to_lat": ride.to_location_lat,
                "to_lng": ride.to_location_lng
            })

            start_time = ride.ride_time
            end_time = ride.to_location_estimated_arrival_time

        # Handle start and end time display
        if start_time:
            response_data["ride_details"]["start_time"] = start_time.strftime('%H:%M:%S')
        if end_time:
            response_data["ride_details"]["end_time"] = end_time.strftime('%H:%M:%S')

        if start_time and end_time:
            if isinstance(start_time, time) and isinstance(end_time, time):
                start_datetime = datetime.combine(ride.ride_date, start_time)
                end_datetime = datetime.combine(ride.ride_date, end_time)
                duration = end_datetime - start_datetime
                total_minutes = duration.total_seconds() / 60
                response_data["ride_details"]["duration"] = self.get_duration_format(total_minutes)

        creator = ride.user
        avg_rating = None
        vehicle_name = None
        rating_user_count = 0 

        if creator.role == 'rider':
            avg_rating = RiderRating.objects.filter(rider=creator).aggregate(avg_rating=Avg('rating'))['avg_rating']
            rating_user_count = RiderRating.objects.filter(
                rider=creator
            ).values('rated_by').distinct().count()
            if ride.vehicle:
                vehicle_name = ride.vehicle.model_name
        else:
            try:
                vehicle_info = DriverVehicleInfo.objects.get(user=creator)
                vehicle_name = f"{vehicle_info.car_company} {vehicle_info.car_model}"
                avg_rating = DriverRating.objects.filter(driver=creator).aggregate(avg_rating=Avg('rating'))['avg_rating']
                rating_user_count = DriverRating.objects.filter(
                    driver=creator
                    ).values('rated_by').distinct().count()
            except DriverVehicleInfo.DoesNotExist:
                pass
        cancellation_count = RideShareBooking.objects.filter(
            user=creator, status="cancelled"
            ).count()
        if cancellation_count == 0:
            cancellation_message = "No cancellation record."
        elif cancellation_count <= 10:
            cancellation_message = f"Rarely cancels rides"
        else:
            cancellation_message = f"High cancellation history"
        response_data["ride_creator"].update({
            "username": creator.username,
            "phone_number": creator.phone_number,
            "profile_image": request.build_absolute_uri(creator.profile.url) if creator.profile else None,
            "avg_rating": round(float(avg_rating), 1) if avg_rating is not None else None,
            "vehicle_name": vehicle_name,
            "rating_user_count": rating_user_count,
            "cancellation_probability": cancellation_message
        })

        passengers = []
        accepted_requests = ride.join_requests.filter(status='accepted').select_related('user', 'segment')

        for req in accepted_requests:
            if req.user == ride.user:
                continue

            passenger_data = {
                "username": req.user.username,
                "profile_image": request.build_absolute_uri(req.user.profile.url) if req.user.profile else None,
                "from_location": req.segment.from_stop if req.segment else ride.from_location,
                "to_location": req.segment.to_stop if req.segment else ride.to_location
            }
            passengers.append(passenger_data)

        response_data["other_passengers"] = passengers

        return Response({
            "status": True,
            "message": "Ride details fetched successfully.",
            "data": response_data
        }, status=status.HTTP_200_OK)

    

class RideStartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            booking = RideShareBooking.objects.get(id=ride_id, user=request.user)
        except RideShareBooking.DoesNotExist:
            return Response({"detail": "Ride not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        if booking.status != 'published':
            return Response({"detail": "Ride cannot be started in current status."}, status=status.HTTP_400_BAD_REQUEST)

        # Set start datetime and update status
        booking.ride_start_datetime = timezone.now()
        booking.status = 'in_progress'
        booking.save()

        return Response({
            "detail": "Ride started successfully.",
            "ride_start_datetime": convert_to_ist(booking.ride_start_datetime),
            "status": booking.status,
            "ride_creator_role":request.user.role,
        }, status=status.HTTP_200_OK)


class MarkReachedDestinationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideShareBooking.objects.get(id=ride_id)
        except RideShareBooking.DoesNotExist:
            return Response({"error": "Ride not found"}, status=status.HTTP_404_NOT_FOUND)

        if ride.user != request.user and not request.user.is_staff:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        ride.reached_destination = True
        ride.ride_end_datetime = timezone.now()
        ride.save()

        # ✅ Send WebSocket message to passenger
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{ride.user.id}",  # Group name based on passenger user ID
            {
                "type": "ride.destination_reached",
                "ride_id": ride.id,
                "message": "Driver has reached the destination.",
                "timestamp": str(ride.ride_end_datetime),
            }
        )

        return Response({"success": True, "message": "Destination marked and notification sent."})


class RideEndAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            booking = RideShareBooking.objects.get(id=ride_id, user=request.user)
        except RideShareBooking.DoesNotExist:
            return Response({"detail": "Ride not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        if booking.status != 'in_progress':
            return Response({"detail": "Ride cannot be ended in current status."}, status=status.HTTP_400_BAD_REQUEST)

        # Set end datetime and update status
        booking.ride_end_datetime = timezone.now()
        booking.status = 'completed'
        booking.save()

        return Response({
            "detail": "Ride ended successfully.",
            "ride_end_datetime": convert_to_ist(booking.ride_end_datetime),
            "status": booking.status
        }, status=status.HTTP_200_OK)

class RidePaymentSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, join_request_id):
        try:
            join_request = RideJoinRequest.objects.select_related('ride', 'segment', 'user').get(
                id=join_request_id, user=request.user
            )
        except RideJoinRequest.DoesNotExist:
            return Response(
                {"status": False, "message": "Join request not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        ride = join_request.ride
        seats = join_request.seats_requested

        # Get price from segment or full ride
        if join_request.segment:
            price_per_seat = float(join_request.segment.price)
            from_location = join_request.segment.from_stop
            to_location = join_request.segment.to_stop
        else:
            price_per_seat = float(ride.price) if ride.price else 0.0
            from_location = ride.from_location
            to_location = ride.to_location

        # Round off
        price_per_seat_rounded = int(round(price_per_seat))
        total_price = int(round(seats * price_per_seat))

        return Response({
            "status": True,
            "message": "Payment summary fetched successfully.",
            "data": {
                "ride_id": ride.id,
                "from": from_location,
                "to": to_location,
                "ride_date": ride.ride_date.strftime('%Y-%m-%d'),
                "ride_time": ride.ride_time.strftime('%H:%M:%S'),
                "driver_name": ride.user.username,
                "driver_role": ride.user.role,  # 👈 Added publisher role
                "seats_requested": seats,
                "price_per_seat": price_per_seat_rounded,
                "total_amount": total_price,
                "segment_id": join_request.segment.id if join_request.segment else None
            }
        }, status=status.HTTP_200_OK)


class CompleteRideShareBookingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        try:
            ride = RideShareBooking.objects.get(id=ride_id)
        except RideShareBooking.DoesNotExist:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only the ride creator or staff can mark as completed
        if request.user != ride.user and not request.user.is_staff:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

        if ride.status == 'completed':
            return Response({'message': 'Ride is already completed.'}, status=status.HTTP_200_OK)

        # Update status and end time
        ride.status = 'completed'
        ride.ride_end_datetime = timezone.now()
        ride.save()

        return Response({'message': 'Ride marked as completed successfully.'}, status=status.HTTP_200_OK)
    

class RateRideAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_join_request_id):
        serializer = RatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rating = serializer.validated_data['rating']
        review = serializer.validated_data.get('review', '')

        user = request.user

        try:
            join_request = RideJoinRequest.objects.get(id=ride_join_request_id)

            if join_request.status != 'accepted':
                return Response({"error": "Only accepted rides can be rated."}, status=400)

            ride = join_request.ride  # RideShareBooking
            publisher = ride.user     # Ride creator

            if publisher == user:
                return Response({"error": "You cannot rate your own ride."}, status=403)

            if ride.status != 'completed':
                return Response({"error": "Cannot rate an incomplete ride."}, status=400)

            if publisher.role == 'driver':
                # Prevent duplicate rating
                if DriverRating.objects.filter(ride_sharing=join_request, driver=publisher, rated_by=user).exists():
                    return Response({"error": "You have already rated this driver."}, status=400)

                DriverRating.objects.create(
                    ride_sharing=join_request,
                    driver=publisher,
                    rated_by=user,
                    rating=rating,
                    review=review
                )
                return Response({"message": "Driver rated successfully."})

            elif publisher.role == 'rider':
                if RiderRating.objects.filter(ride_sharing=join_request, rider=publisher, rated_by=user).exists():
                    return Response({"error": "You have already rated this rider."}, status=400)

                RiderRating.objects.create(
                    ride_sharing=join_request,
                    rider=publisher,
                    rated_by=user,
                    rating=rating,
                    review=review
                )
                return Response({"message": "Rider rated successfully."})

            return Response({"error": "Invalid publisher role."}, status=400)

        except RideJoinRequest.DoesNotExist:
            return Response({"error": "RideJoinRequest not found."}, status=404)


class CancelRideJoinRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            join_request = RideJoinRequest.objects.get(pk=pk, user=request.user)
        except RideJoinRequest.DoesNotExist:
            return Response({"status": False, "message": "Join request not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

        if join_request.status not in ['pending', 'accepted']:
            return Response({"status": False, "message": f"Cannot cancel a '{join_request.status}' request."}, status=status.HTTP_400_BAD_REQUEST)

        join_request.status = 'cancelled'
        join_request.save()

        return Response({"status": True, "message": "Join request cancelled successfully."}, status=status.HTTP_200_OK)
    

class InProgressRidesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ✅ Only rides that are in_progress and associated with this user
        rides = RideShareBooking.objects.filter(
            status="in_progress"
        ).filter(
            Q(user=user) | Q(join_requests__user=user)
        ).distinct()

        serializer = InProgressRideSerializer(rides, many=True, context={"request": request})
        return Response(serializer.data)



# payment
class RideSharePaymentAPIView(APIView):
    """
    Accepts payment for a ride sharing join request by the authenticated user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, ride_id):
        user = request.user
        data = request.data
        payment_method = data.get('payment_method')
        amount = data.get('amount_paid')
        transaction_id = data.get('transaction_id', None)

        if not payment_method or not amount:
            return Response({"error": "payment_method and amount_paid are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if payment_method == 'upi' and not transaction_id:
            return Response({"error": "transaction_id is required for UPI payments."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            ride = RideShareBooking.objects.get(id=ride_id)
            join_request = RideJoinRequest.objects.get(ride=ride, user=user)
        except RideShareBooking.DoesNotExist:
            return Response({"error": "Ride not found."}, status=status.HTTP_404_NOT_FOUND)
        except RideJoinRequest.DoesNotExist:
            return Response({"error": "Join request not found for this user."},
                            status=status.HTTP_404_NOT_FOUND)

        # Fetch driver safely
        driver = None
        if ride.vehicle:
            if hasattr(ride.vehicle, 'driver'):
                driver = ride.vehicle.driver
            elif hasattr(ride.vehicle, 'user'):
                driver = ride.vehicle.user

        if not driver:
            # fallback: try DriverVehicleInfo mapping
            try:
                driver_vehicle = DriverVehicleInfo.objects.get(user=ride.user)
                driver = driver_vehicle.user
            except DriverVehicleInfo.DoesNotExist:
                return Response({"error": "Driver not assigned for this ride."},
                                status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Platform fee calculation
            platform_fee_amount = 0
            platform_fee_obj = PlatformSetting.objects.filter(fee_reason='platform fee', is_active=True).first()
            if platform_fee_obj:
                if platform_fee_obj.fee_type == 'percentage':
                    platform_fee_amount = float(amount) * float(platform_fee_obj.fee_value) / 100
                else:
                    platform_fee_amount = float(platform_fee_obj.fee_value)

            # Add pending fee for driver
            if platform_fee_amount > 0:
                DriverPendingFee.objects.create(
                    driver=driver,
                    shared_ride=ride,
                    amount=platform_fee_amount
                )

            # Deduct pending fees if UPI
            try:
                # Prevent duplicate UPI transaction
                if payment_method == 'upi' and SharedRidePayment.objects.filter(transaction_id=transaction_id).exists():
                    return Response(
                        {"error": "This UPI transaction has already been submitted."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Create payment record
                payment = SharedRidePayment.objects.create(
                    ride=ride,
                    driver=driver,
                    join_request=join_request,
                    amount_paid=amount,
                    payment_method=payment_method,
                    transaction_id=transaction_id,
                    is_verified=(payment_method == 'upi')
                )

            except IntegrityError:
                return Response(
                    {"error": "Payment already exists or transaction ID conflict."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Auto-accept join request if UPI
            if payment_method == 'upi':
                join_request.status = 'accepted'
                join_request.save()

                # Send WebSocket notification to driver
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'driver_{driver.id}',
                    {
                        'type': 'payment_notification',
                        'message': f'UPI Payment of ₹{amount} received for Ride {ride.id}'
                    }
                )

        return Response({
            "success": True,
            "payment_id": payment.id,
            "is_verified": payment.is_verified,
            "platform_fee": platform_fee_amount
        }, status=status.HTTP_201_CREATED)

class RideShareCashVerifyAPIView(APIView):
    """
    Driver manually verifies cash received for a join request
    """

    def post(self, request, payment_id):
        try:
            payment = SharedRidePayment.objects.get(id=payment_id)
        except SharedRidePayment.DoesNotExist:
            return Response({"error": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        if payment.payment_method != 'cash':
            return Response({"error": "Only cash payments can be verified here."}, status=status.HTTP_400_BAD_REQUEST)

        payment.is_verified = True
        payment.save()

        # Update join request status
        payment.join_request.status = 'accepted'
        payment.join_request.save()

        return Response({"success": f"Cash payment of ₹{payment.amount_paid} verified."}, status=status.HTTP_200_OK)
