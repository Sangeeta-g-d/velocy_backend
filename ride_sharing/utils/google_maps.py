import requests
from django.conf import settings

def get_route_segments_with_distance(from_lat, from_lng, to_lat, to_lng, stops):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    waypoints = '|'.join([f"{s['lat']},{s['lng']}" for s in stops])

    params = {
        "origin": f"{from_lat},{from_lng}",
        "destination": f"{to_lat},{to_lng}",
        "waypoints": waypoints,
        "key": settings.GOOGLE_MAPS_API_KEY,
        "units": "metric"
    }

    response = requests.get(url, params=params)
    data = response.json()

    segments = []
    try:
        legs = data['routes'][0]['legs']

        all_points = [{'name': 'FROM'}] + stops + [{'name': 'TO'}]

        for i, leg in enumerate(legs):
            distance_km = round(leg['distance']['value'] / 1000.0, 2)
            duration_seconds = leg['duration']['value']
            from_name = all_points[i]['name']
            to_name = all_points[i + 1]['name']
            segments.append({
                'from_stop': from_name,
                'to_stop': to_name,
                'distance_km': distance_km,
                'duration_seconds': duration_seconds
            })
    except Exception as e:
        print("[ERROR] Failed to extract route segments:", e)
    return segments


