from celery import shared_task
from django.utils import timezone
from .models import RideRequest
from notifications.fcm import send_fcm_notification
from datetime import timedelta

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



@shared_task
def notify_scheduled_rides():
    now = timezone.now()
    reminder_time = now + timedelta(minutes=15)

    rides = RideRequest.objects.filter(
        ride_type="scheduled",
        scheduled_time__range=(now, reminder_time),
        status__in=["accepted", "pending"]  # only upcoming
    )

    for ride in rides:
        # Notify Rider
        send_fcm_notification(
            user=ride.user,
            title="🚖 Ride Reminder",
            body=f"Your scheduled ride from {ride.from_location} to {ride.to_location} starts in 15 minutes.",
            data={
                "ride_id": str(ride.id),
                "type": "ride_reminder",
                "role": "rider"
            }
        )

        # Notify Driver (if assigned)
        if ride.driver:
            send_fcm_notification(
                user=ride.driver,
                title="🚖 Upcoming Ride",
                body=f"You have a scheduled ride starting in 15 minutes from {ride.from_location}.",
                data={
                    "ride_id": str(ride.id),
                    "type": "ride_reminder",
                    "role": "driver"
                }
            )