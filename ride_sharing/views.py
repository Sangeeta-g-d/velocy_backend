from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .serializers import *
from .mixins import StandardResponseMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from datetime import datetime, time
from . models import *
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

                # ❌ Skip full A → B (main ride path)
                if (from_stop['location'] == booking.from_location and
                    to_stop['location'] == booking.to_location):
                    continue

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

        print(f"[DEBUG] Total segments created: {created_count}, skipped: {skipped_count}")

        return self.response({
            'message': 'Stop added and route segments updated successfully.',
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