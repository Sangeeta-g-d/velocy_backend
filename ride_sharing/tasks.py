from decimal import Decimal
from celery import shared_task
from .models import RideShareBooking, RideShareRouteSegment, RideSharePriceSetting
from .utils.google_maps import get_route_segments_with_distance


@shared_task
def calculate_segments_and_eta(booking_id):
    try:
        booking = RideShareBooking.objects.get(id=booking_id)
    except RideShareBooking.DoesNotExist:
        print(f"[TASK] Booking ID {booking_id} not found.")
        return

    # 1. Prepare list of all stops: origin, stops, destination
    stops = list(booking.stops.order_by('order'))

    points = [{
        'name': booking.from_location,
        'lat': booking.from_location_lat,
        'lng': booking.from_location_lng
    }]
    points += [{
        'name': stop.stop_location,
        'lat': stop.stop_lat,
        'lng': stop.stop_lng
    } for stop in stops]
    points.append({
        'name': booking.to_location,
        'lat': booking.to_location_lat,
        'lng': booking.to_location_lng
    })

    # 2. Get route segments from Google Maps
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

    # 3. Compute cumulative distances
    cumulative_distances = [0]
    total = 0
    for seg in segments:
        total += seg['distance_km']
        cumulative_distances.append(total)

    # 4. Delete old segments
    booking.route_segments.all().delete()

    # 5. Create segments i → j
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            from_stop = points[i]['name']
            to_stop = points[j]['name']
            distance_km = round(cumulative_distances[j] - cumulative_distances[i], 2)
            price = round(Decimal(str(distance_km)) * price_setting.min_price_per_km, 2)

            RideShareRouteSegment.objects.create(
                ride_booking=booking,
                from_stop=from_stop,
                to_stop=to_stop,
                distance_km=distance_km,
                price=price
            )

    print(f"[TASK] All segments stored for booking {booking_id}")
