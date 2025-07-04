from .models import CarPoolRide, RideStop

def get_location_options_for_segments(ride_id):
    try:
        ride = CarPoolRide.objects.get(id=ride_id)
    except CarPoolRide.DoesNotExist:
        return []

    location_points = []

    location_points.append({'name': ride.start_location_name})
    stops = RideStop.objects.filter(ride=ride).order_by('order')
    for stop in stops:
        location_points.append({'name': stop.location_name})
    location_points.append({'name': ride.end_location_name})

    segments = []
    for i in range(len(location_points)):
        for j in range(i + 1, len(location_points)):
            segments.append({
                'from_location_name': location_points[i]['name'],
                'to_location_name': location_points[j]['name']
            })
    return segments
