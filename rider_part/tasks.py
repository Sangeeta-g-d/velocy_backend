from celery import shared_task
from django.utils import timezone
from .models import RideRequest

@shared_task
def delete_unaccepted_ride(ride_id):
    try:
        ride = RideRequest.objects.get(id=ride_id)
        # Only delete if still pending and no driver assigned
        if ride.status == "pending" and ride.driver is None:
            ride.delete()
            return f"Ride {ride_id} deleted after timeout"
        return f"Ride {ride_id} was accepted before timeout"
    except RideRequest.DoesNotExist:
        return f"Ride {ride_id} already deleted"
