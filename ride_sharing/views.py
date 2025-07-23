from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from .tasks import calculate_segments_and_eta
from .mixins import StandardResponseMixin
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
    
class CreateRideShareBookingAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        print("[DEBUG] Requesting user:", user, "| Role:", user.role)
        data = request.data.copy()
        print("[DEBUG] Incoming POST data:", data)

        if user.role == 'driver':
            try:
                vehicle_info = DriverVehicleInfo.objects.get(user=user)
                print("[DEBUG] Driver vehicle info found:", vehicle_info)
            except DriverVehicleInfo.DoesNotExist:
                return self.response({"error": "Driver vehicle info not found."}, status_code=404)

            data['vehicle_number'] = vehicle_info.vehicle_number
            data['model_name'] = vehicle_info.car_model
            data['seat_capacity'] = 4  # You can update to dynamic if needed
            print("[DEBUG] Populated driver vehicle data:", {
                "vehicle_number": data['vehicle_number'],
                "model_name": data['model_name'],
                "seat_capacity": data['seat_capacity'],
            })

        else:
            vehicle_id = data.get('vehicle')
            print("[DEBUG] Rider submitted vehicle ID:", vehicle_id)
            if not vehicle_id:
                return self.response({"error": "Vehicle ID is required for rider."}, status_code=400)

            try:
                vehicle = RideShareVehicle.objects.get(id=vehicle_id, owner=user)
                print("[DEBUG] Vehicle found and owned by user:", vehicle)
            except RideShareVehicle.DoesNotExist:
                return self.response({"error": "Vehicle not found or access denied."}, status_code=404)

            if not vehicle.approved:
                return self.response({"error": "Vehicle is not approved yet."}, status_code=400)

            data['vehicle'] = vehicle.id
            data['vehicle_number'] = vehicle.vehicle_number
            data['model_name'] = vehicle.model_name
            data['seat_capacity'] = vehicle.seat_capacity
            print("[DEBUG] Populated rider vehicle data:", {
                "vehicle": vehicle.id,
                "vehicle_number": vehicle.vehicle_number,
                "model_name": vehicle.model_name,
                "seat_capacity": vehicle.seat_capacity,
            })

        serializer = RideShareBookingCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            booking = serializer.save()
            print("[DEBUG] Booking created successfully:", booking)
            return self.response({
                'booking_id': booking.id,
                'status': booking.status,
                'message': 'Ride booking created in draft status.'
            }, status_code=201)

        print("[ERROR] Serializer errors:", serializer.errors)
        return self.response(serializer.errors, status_code=400)


class AddRideShareStopAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = RideShareBooking.objects.get(id=booking_id, user=request.user)
        except RideShareBooking.DoesNotExist:
            return self.response({'error': 'Ride booking not found or access denied.'}, status_code=404)

        serializer = RideShareStopCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.response(serializer.errors, status_code=400)

        stop = serializer.save(ride_booking=booking)

        # 🚀 Offload route & ETA calculation to Celery
        calculate_segments_and_eta.delay(booking.id)

        return self.response({
            'message': 'Stop added. Route and arrival time will be updated shortly.',
            'stop': serializer.data
        }, status_code=201)


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

        ride.price = serializer.validated_data['price']
        ride.save()

        return self.response({
            "message": "Ride price updated successfully.",
            "ride_id": ride.id,
            "updated_price": ride.price
        }, status_code=HTTP_200_OK)
    

class UpdateReturnRideDetailsAPIView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, ride_id):
        booking = get_object_or_404(RideShareBooking, id=ride_id, user=request.user)
        
        serializer = RideReturnDetailsSerializer(instance=booking, data=request.data, partial=True)
        if serializer.is_valid():
            updated_booking = serializer.save()
            return self.response({
                "message": "Return ride details updated successfully.",
                "return_details": RideReturnDetailsSerializer(updated_booking).data
            })
        return self.response(serializer.errors, status_code=400)
    
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

        stop_data = RideShareStopSerializer(stops, many=True).data
        segment_data = RideShareSegmentPriceSerializer(segments, many=True).data

        return self.response({
            "stops": stop_data,
            "segments": segment_data
        })

class RideShareSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from_location = request.query_params.get('from')
        to_location = request.query_params.get('to')
        date = request.query_params.get('date')
        time = request.query_params.get('time')
        seats_required = int(request.query_params.get('seats', 1))

        if not from_location or not to_location:
            return Response({
                "status": False,
                "message": "Both 'from' and 'to' locations are required."
            }, status=status.HTTP_400_BAD_REQUEST)

        booking_filters = (
            Q(status="published") &
            Q(seats_remaining__gte=seats_required) &
            ~Q(user=request.user)
        )
        if date:
            booking_filters &= Q(ride_date=date)
        if time:
            booking_filters &= Q(ride_time__gte=time)

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
            Q(from_stop__iexact=from_location) & Q(to_stop__iexact=to_location)
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
                    ride_booking=ride, stop_location__iexact=matching_segment.from_stop
                ).first()
                from_arrival_time = (
                    from_stop_obj.estimated_arrival_time.strftime('%H:%M:%S')
                    if from_stop_obj and from_stop_obj.estimated_arrival_time else None
                )

            # Get to_arrival_time
            to_stop_obj = RideShareStop.objects.filter(
                ride_booking=ride, stop_location__iexact=matching_segment.to_stop
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
                "avg_rating": float(avg_rating) if avg_rating else None,
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
        message = request.data.get('message', '')

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
            message=message
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
    
class RideJoinRequestsByRideView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ride_id):
        try:
            ride = RideShareBooking.objects.get(id=ride_id, user=request.user)
        except RideShareBooking.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Ride not found or access denied.'
            }, status=status.HTTP_404_NOT_FOUND)

        join_requests = (
            RideJoinRequest.objects
            .filter(ride=ride)
            .select_related('user', 'segment')
        )
        serializer = RideJoinRequestViewSerializer(
            join_requests,
            many=True,
            context={'request': request, 'ride': ride}
        )

        return Response({
            'status': True,
            'message': 'Join requests found.',
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
        serializer = RideJoinRequestDetailSerializer(join_requests, many=True)
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
            "cancellation_probability": float(ride.cancellation_probability) if ride.cancellation_probability else None,
            "ride_creator": {},
            "ride_details": {
                "duration": None
            },
            "coordinates": {}
        }

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

                # Coordinates and duration
                if segment.from_stop.lower() == ride.from_location.lower():
                    response_data["coordinates"].update({
                        "from_lat": ride.from_location_lat,
                        "from_lng": ride.from_location_lng
                    })
                    start_time = ride.ride_time
                else:
                    from_stop = RideShareStop.objects.filter(
                        ride_booking=ride,
                        stop_location__iexact=segment.from_stop
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
                        stop_location__iexact=segment.to_stop
                    ).first()
                    if to_stop:
                        response_data["coordinates"].update({
                            "to_lat": to_stop.stop_lat,
                            "to_lng": to_stop.stop_lng
                        })
                        end_time = to_stop.estimated_arrival_time

                if start_time and end_time:
                    if isinstance(start_time, time) and isinstance(end_time, time):
                        start_datetime = datetime.combine(ride.ride_date, start_time)
                        end_datetime = datetime.combine(ride.ride_date, end_time)
                        duration = end_datetime - start_datetime
                        total_minutes = duration.total_seconds() / 60
                        response_data["ride_details"]["duration"] = self.get_duration_format(total_minutes)

            except RideShareRouteSegment.DoesNotExist:
                return Response({
                    "status": False,
                    "message": "Segment not found for this ride."
                }, status=status.HTTP_404_NOT_FOUND)

        else:
            # ✅ Fetch price from model directly
            ride_price = float(ride.price) if ride.price is not None else 0.0

            response_data["ride_details"].update({
                "from_location": ride.from_location,
                "to_location": ride.to_location,
                "distance_km": float(ride.distance_km) if ride.distance_km is not None else None,
                "price": ride_price,
                "total_price": ride_price
            })

            response_data["coordinates"].update({
                "from_lat": ride.from_location_lat,
                "from_lng": ride.from_location_lng,
                "to_lat": ride.to_location_lat,
                "to_lng": ride.to_location_lng
            })

            if ride.ride_time and ride.to_location_estimated_arrival_time:
                start_datetime = datetime.combine(ride.ride_date, ride.ride_time)
                end_datetime = datetime.combine(ride.ride_date, ride.to_location_estimated_arrival_time)
                duration = end_datetime - start_datetime
                total_minutes = duration.total_seconds() / 60
                response_data["ride_details"]["duration"] = self.get_duration_format(total_minutes)

        # 🚘 Ride creator info
        creator = ride.user
        avg_rating = None
        vehicle_name = None

        if creator.role == 'rider':
            avg_rating = RiderRating.objects.filter(rider=creator).aggregate(avg_rating=Avg('rating'))['avg_rating']
            if ride.vehicle:
                vehicle_name = ride.vehicle.model_name
        else:
            try:
                vehicle_info = DriverVehicleInfo.objects.get(user=creator)
                vehicle_name = f"{vehicle_info.car_company} {vehicle_info.car_model}"
            except DriverVehicleInfo.DoesNotExist:
                pass

        response_data["ride_creator"].update({
            "username": creator.username,
            "phone_number": creator.phone_number,
            "profile_image": request.build_absolute_uri(creator.profile.url) if creator.profile else None,
            "avg_rating": float(avg_rating) if avg_rating is not None else None,
            "vehicle_name": vehicle_name
        })

        # 👥 Add accepted passengers' details
        passengers = []
        accepted_requests = ride.join_requests.filter(status='accepted').select_related('user', 'segment')

        for req in accepted_requests:
            if req.user == ride.user:
                continue  # Skip ride creator

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
