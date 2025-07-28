from decimal import Decimal
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from .models import (
    RideShareBooking,
    RideShareRouteSegment,
    RideSharePriceSetting,
    RideShareStop
)
from .utils.google_maps import get_route_segments_with_distance


@shared_task
def calculate_segments_and_eta(booking_id):
    try:
        booking = RideShareBooking.objects.get(id=booking_id)
    except RideShareBooking.DoesNotExist:
        print(f"[TASK] Booking ID {booking_id} not found.")
        return

    # Prepare points: origin, stops, and destination
    stops = list(booking.stops.order_by('order'))

    points = [{
        'name': booking.from_location,
        'lat': booking.from_location_lat,
        'lng': booking.from_location_lng
    }] + [{
        'name': stop.stop_location,
        'lat': stop.stop_lat,
        'lng': stop.stop_lng,
        'stop_id': stop.id
    } for stop in stops] + [{
        'name': booking.to_location,
        'lat': booking.to_location_lat,
        'lng': booking.to_location_lng
    }]

    if any(p['lat'] is None or p['lng'] is None for p in points):
        print("[TASK] Invalid coordinates found in points.")
        return

    if len(points) > 25:
        print("[TASK] Too many points. Google API allows only 25 (including origin/destination).")
        return

    # Get route segments using Google Maps API
    segments = get_route_segments_with_distance(
        from_lat=points[0]['lat'],
        from_lng=points[0]['lng'],
        to_lat=points[-1]['lat'],
        to_lng=points[-1]['lng'],
        stops=points[1:-1]
    )

    if len(segments) != len(points) - 1:
        print("[TASK] Segment count mismatch. Skipping route update.")
        return

    price_setting = RideSharePriceSetting.objects.first()
    if not price_setting:
        print("[TASK] No RideSharePriceSetting found.")
        return

    # Calculate cumulative distances and durations
    cumulative_distances = [0]
    cumulative_durations = [0]
    total_dist = 0
    total_time = 0

    for seg in segments:
        total_dist += seg['distance_km']
        total_time += seg['duration_seconds']
        cumulative_distances.append(total_dist)
        cumulative_durations.append(total_time)

    # Clear existing segments
    booking.route_segments.all().delete()

    # Store new route segments
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            from_stop = points[i]['name']
            to_stop = points[j]['name']

            if from_stop == booking.from_location and to_stop == booking.to_location:
                continue

            distance_km = round(cumulative_distances[j] - cumulative_distances[i], 2)
            price = round(Decimal(str(distance_km)) * price_setting.min_price_per_km, 2)

            RideShareRouteSegment.objects.create(
                ride_booking=booking,
                from_stop=from_stop,
                to_stop=to_stop,
                distance_km=distance_km,
                price=price
            )

    # Calculate ETA for each stop
    ride_start_time = datetime.combine(timezone.now().date(), booking.ride_time)
    for index, stop in enumerate(stops):
        eta_seconds = cumulative_durations[index + 1]  # +1 because index 0 is origin
        stop.estimated_arrival_time = ride_start_time + timedelta(seconds=eta_seconds)
        stop.save()

    print(f"[TASK] Segments and ETA stored for booking {booking_id}")


@shared_task
def test_task():
    print("Test task executed.")
    return "Done"
