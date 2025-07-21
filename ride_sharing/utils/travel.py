from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def calculate_eta(distance_km, ride_time, avg_speed_kmph=40):
    """
    Calculate estimated arrival time based on distance and average speed.

    :param distance_km: float - distance in kilometers
    :param ride_time: datetime.time object - departure time
    :param avg_speed_kmph: int - average speed (default 40 km/h)
    :return: datetime.time object - estimated arrival time
    """
    try:
        if not distance_km or not ride_time:
            return None

        travel_hours = float(distance_km) / avg_speed_kmph
        ride_datetime = datetime.combine(datetime.today(), ride_time)
        estimated_arrival = ride_datetime + timedelta(hours=travel_hours)
        return estimated_arrival.time()
    except Exception as e:
        logger.error(f"[ETA ERROR]: Failed to calculate ETA: {e}")
        return None
