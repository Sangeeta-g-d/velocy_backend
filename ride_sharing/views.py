from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from .mixins import StandardResponseMixin
from datetime import datetime, timedelta
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from datetime import datetime, time
from rest_framework.response import Response
from rest_framework import status
from . models import *
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from decimal import Decimal
from pytz import timezone as pytz_timezone
from django.utils import timezone
from decimal import Decimal
from .utils.google_maps import get_driving_distance_km
from django.db.models import Q
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

    def post(self, request, vehicle_id):
        try:
            vehicle = RideShareVehicle.objects.get(id=vehicle_id)
        except RideShareVehicle.DoesNotExist:
            return self.response({"error": "Vehicle not found."}, status_code=404)

        if not vehicle.approved:
            return self.response({"error": "Vehicle is not approved yet."}, status_code=400)

        data = request.data.copy()
        data['vehicle'] = vehicle.id  # Inject vehicle ID into serializer data

        serializer = RideShareBookingCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            booking = serializer.save()
            return self.response({
                'booking_id': booking.id,
                'status': booking.status,
                'message': 'Ride booking created in draft status.'
            }, status_code=201)

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
        print(f"[DEBUG] Stop '{stop.stop_location}' added with order {stop.order} for booking {booking.id}")

        # Fetch price setting
        price_setting = RideSharePriceSetting.objects.first()
        if not price_setting:
            print("[DEBUG] No price setting found.")
            return self.response({'error': 'Price settings not configured.'}, status_code=500)

        # Prepare full route with from_location, stops, to_location
        stops = list(booking.stops.order_by('order'))
        print(f"[DEBUG] Total stops after save: {len(stops)}")

        virtual_stops = [{
            'location': booking.from_location,
            'lat': booking.from_location_lat,
            'lng': booking.from_location_lng
        }]
        for s in stops:
            virtual_stops.append({
                'location': s.stop_location,
                'lat': s.stop_lat,
                'lng': s.stop_lng
            })
        virtual_stops.append({
            'location': booking.to_location,
            'lat': booking.to_location_lat,
            'lng': booking.to_location_lng
        })

        created_count = 0
        skipped_count = 0

        for i in range(len(virtual_stops)):
            for j in range(i + 1, len(virtual_stops)):
                from_stop = virtual_stops[i]
                to_stop = virtual_stops[j]

                if (from_stop['location'] == booking.from_location and
                    to_stop['location'] == booking.to_location):
                    continue  # Skip full A→B path

                print(f"[DEBUG] Processing segment: {from_stop['location']} → {to_stop['location']}")

                distance = get_driving_distance_km(
                    from_stop['lat'], from_stop['lng'],
                    to_stop['lat'], to_stop['lng']
                )

                if distance is not None:
                    distance_decimal = Decimal(str(distance))
                    price = distance_decimal * price_setting.min_price_per_km

                    RideShareRouteSegment.objects.update_or_create(
                        ride_booking=booking,
                        from_stop=from_stop['location'],
                        to_stop=to_stop['location'],
                        defaults={
                            'distance_km': round(distance_decimal, 2),
                            'price': round(price, 2)
                        }
                    )
                    print(f"[DEBUG] Created segment {from_stop['location']} → {to_stop['location']} | Distance: {distance_decimal} km | Price: ₹{price}")
                    created_count += 1
                else:
                    print(f"[DEBUG] Skipped segment {from_stop['location']} → {to_stop['location']} (distance=None)")
                    skipped_count += 1

        # === Estimate Arrival Times ===
        AVG_SPEED_KMPH = 40  # Configurable default

        current_time = datetime.combine(datetime.today(), booking.ride_time)
        stop_times = []

        for i in range(len(virtual_stops)):
            from_stop = virtual_stops[i]

            if i == 0:
                arrival_time = current_time.time()
            else:
                prev_stop = virtual_stops[i - 1]
                dist = get_driving_distance_km(
                    prev_stop['lat'], prev_stop['lng'],
                    from_stop['lat'], from_stop['lng']
                )
                if dist is not None:
                    travel_hours = dist / AVG_SPEED_KMPH
                    delta = timedelta(hours=travel_hours)
                    current_time += delta
                arrival_time = current_time.time()

            stop_times.append(arrival_time)

        # Save arrival times to RideShareStop
        for stop_obj, arrival_time in zip(stops, stop_times[1:-1]):  # Skip 'from' and 'to'
            stop_obj.estimated_arrival_time = arrival_time
            stop_obj.save()

        # Save final destination arrival time
        booking.to_location_estimated_arrival_time = stop_times[-1]
        booking.save()

        print(f"[DEBUG] Total segments created: {created_count}, skipped: {skipped_count}")
        print(f"[DEBUG] Arrival at final destination: {booking.to_location_estimated_arrival_time}")

        return self.response({
            'message': 'Stop added and route segments & arrival times updated successfully.',
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

        # --- 1. Direct Rides ---
        direct_rides = RideShareBooking.objects.filter(
            booking_filters &
            Q(from_location__iexact=from_location) &
            Q(to_location__iexact=to_location)
        ).select_related('user')

        for ride in direct_rides:
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
                "segment_id": None  # Explicitly show None for direct rides
            })

        # --- 2. Segment-Based Rides ---
        segment_qs = RideShareRouteSegment.objects.filter(
            Q(from_stop__iexact=from_location) & Q(to_stop__iexact=to_location)
        )
        segment_ride_ids = segment_qs.values_list('ride_booking_id', flat=True)

        segment_rides = RideShareBooking.objects.filter(
            booking_filters & Q(id__in=segment_ride_ids)
        ).select_related('user')

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

        join_requests = RideJoinRequest.objects.filter(ride=ride).select_related('user', 'segment')
        serializer = RideJoinRequestViewSerializer(join_requests, many=True, context={'request': request})

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
            ride = RideShareBooking.objects.get(id=ride_id)
        except RideShareBooking.DoesNotExist:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        accepted_requests = RideJoinRequest.objects.filter(
            ride=ride, status='accepted'
        ).select_related('user', 'segment')

        serializer = AcceptedJoinRequestSerializer(accepted_requests, many=True)
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