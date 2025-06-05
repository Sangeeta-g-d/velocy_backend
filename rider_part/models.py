from django.db import models
from django.contrib.auth import get_user_model
from admin_part.models import City,VehicleType
# Create your models here.
User = get_user_model()

class RideRequest(models.Model):
    RIDE_TYPE_CHOICES = (
        ('now', 'Book Now'),
        ('scheduled', 'Scheduled'),
    )
    STATUS_CHOICES = (
        ('draft', 'Draft'),  # created after confirming from/to
        ('pending', 'Pending'),  # submitted but not accepted
        ('accepted', 'Accepted'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ride_requests')
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True)
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.SET_NULL, null=True)

    ride_type = models.CharField(max_length=10, choices=RIDE_TYPE_CHOICES)
    scheduled_time = models.DateTimeField(blank=True, null=True)

    from_location = models.CharField(max_length=255)
    from_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    from_longitude = models.DecimalField(max_digits=9, decimal_places=6)

    to_location = models.CharField(max_length=255)
    to_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    to_longitude = models.DecimalField(max_digits=9, decimal_places=6)

    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    estimated_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    offered_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    women_only = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    
    driver = models.ForeignKey(User,on_delete=models.SET_NULL,null=True, blank=True, related_name='accepted_rides')

    def __str__(self):
        return f"Ride by {self.user} - {self.from_location} → {self.to_location}"


class RideStop(models.Model):
    ride = models.ForeignKey(RideRequest, on_delete=models.CASCADE, related_name='ride_stops')
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    order = models.PositiveIntegerField(help_text="Stop order")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Stop #{self.order} at {self.location}"