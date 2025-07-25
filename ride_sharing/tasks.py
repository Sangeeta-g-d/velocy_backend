from decimal import Decimal
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from .models import RideShareBooking, RideShareRouteSegment, RideSharePriceSetting, RideShareStop
from .utils.google_maps import get_route_segments_with_distance


@shared_task
def calculate_segments_and_eta(booking_id):
    try:
        booking = RideShareBooking.objects.get(id=booking_id)
    except RideShareBooking.DoesNotExist:
        print(f"[TASK] Booking ID {booking_id} not found.")
        return

    stops = list(booking.stops.order_by('order'))

    points = [{
        'name': booking.from_location,
        'lat': booking.from_location_lat,
        'lng': booking.from_location_lng
    }]
    points += [{
        'name': stop.stop_location,
        'lat': stop.stop_lat,
        'lng': stop.stop_lng,
        'stop_id': stop.id  # for ETA use
    } for stop in stops]
    points.append({
        'name': booking.to_location,
        'lat': booking.to_location_lat,
        'lng': booking.to_location_lng
    })

    print(f"[TASK] Booking {booking_id} - Points:")
    for p in points:
        print(f" - {p['name']} | lat: {p['lat']} | lng: {p['lng']}")

    if any(p['lat'] is None or p['lng'] is None for p in points):
        print("[TASK] Error: One or more points have invalid coordinates.")
        return

    if len(points) > 25:
        print("[TASK] Error: Too many points. Google Directions API supports only 25 total.")
        return

    segments = get_route_segments_with_distance(
        from_lat=points[0]['lat'],
        from_lng=points[0]['lng'],
        to_lat=points[-1]['lat'],
        to_lng=points[-1]['lng'],
        stops=points[1:-1]
    )

    if len(segments) != len(points) - 1:
        print("[TASK] Mismatch in route segments. Skipping.")
        return

    price_setting = RideSharePriceSetting.objects.first()
    if not price_setting:
        print("[TASK] No price setting found.")
        return

    cumulative_distances = [0]
    cumulative_durations = [0]
    total_dist = 0
    total_time = 0

    for seg in segments:
        total_dist += seg['distance_km']
        total_time += seg['duration_seconds']
        cumulative_distances.append(total_dist)
        cumulative_durations.append(total_time)

    booking.route_segments.all().delete()

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

    ride_start_time = datetime.combine(timezone.now().date(), booking.ride_time)

    for index, stop in enumerate(stops):
        eta_seconds = cumulative_durations[index + 1]  # index 0 is origin
        stop.estimated_arrival_time = ride_start_time + timedelta(seconds=eta_seconds)
        stop.save()

    print(f"[TASK] Segments and ETA stored for booking {booking_id}")
