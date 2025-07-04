from django.db import models
from auth_api.models import CustomUser
# Create your models here.

class CarPoolRide(models.Model):
    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='carpool_rides')

    start_location_name = models.CharField(max_length=255)
    start_latitude = models.FloatField()
    start_longitude = models.FloatField()

    end_location_name = models.CharField(max_length=255)
    end_latitude = models.FloatField()
    end_longitude = models.FloatField()

    date = models.DateField()
    time = models.TimeField()

    total_seats = models.PositiveIntegerField()
    available_seats = models.PositiveIntegerField()

    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total price from start to end location"
    )

    estimated_duration = models.DurationField(null=True, blank=True, help_text="Estimated total travel time")
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Distance in kilometers")
    driver_notes = models.TextField(null=True, blank=True, help_text="Optional notes or instructions from the driver")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.driver.name} | {self.start_location_name} → {self.end_location_name} @ {self.date}"


class RideStop(models.Model):
    ride = models.ForeignKey(CarPoolRide, on_delete=models.CASCADE, related_name='stops')
    location_name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()

    order = models.PositiveIntegerField(help_text="Order of the stop along the route")

    class Meta:
        ordering = ['order']

