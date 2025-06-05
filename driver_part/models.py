from django.db import models
from rider_part.models import RideRequest
from auth_api.models import CustomUser
# Create your models here.

class DeclinedRide(models.Model):
    ride = models.ForeignKey(RideRequest, on_delete=models.CASCADE, related_name="declined_by_drivers")
    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="declined_rides")
    declined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ride', 'driver')  # Prevent multiple decline records for same ride-driver
