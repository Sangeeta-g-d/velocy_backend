# utils/google_maps.py

import requests
from django.conf import settings

def get_driving_distance_km(lat1, lng1, lat2, lng2):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{lat1},{lng1}",
        "destinations": f"{lat2},{lng2}",
        "key": settings.GOOGLE_MAPS_API_KEY,
        "units": "metric"
    }
    response = requests.get(url, params=params)
    data = response.json()

    try:
        distance_meters = data['rows'][0]['elements'][0]['distance']['value']
        return round(distance_meters / 1000.0, 2)
    except Exception:
        return None
