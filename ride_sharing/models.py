from django.db import models
from auth_api.models import CustomUser
from django.conf import settings
from django.utils import timezone
# Create your models here.

class RideShareVehicle(models.Model):
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ride_vehicles')
    vehicle_number = models.CharField(max_length=20, unique=True) 
    model_name = models.CharField(max_length=100)
    seat_capacity = models.PositiveIntegerField()

    # Documents
    registration_doc = models.FileField(upload_to='vehicle_docs/', blank=True, null=True)
    aadhar_card = models.FileField(upload_to='ride_aadhar_cards/', blank=True, null=True)
    driving_license = models.FileField(upload_to='ride_driving_licenses/', blank=True, null=True)

    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model_name} ({self.vehicle_number})"


class RideSharePriceSetting(models.Model):
    price_per_km = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"₹{self.price_per_km}/km from {self.effective_from.strftime('%Y-%m-%d')}"


class RideShareBooking(models.Model):
    STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_share_bookings')
    vehicle = models.ForeignKey('RideShareVehicle', on_delete=models.CASCADE, related_name='bookings')

    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    from_location_lat = models.FloatField(null=True, blank=True)
    from_location_lng = models.FloatField(null=True, blank=True)
    to_location_lat = models.FloatField(null=True, blank=True)
    to_location_lng = models.FloatField(null=True, blank=True)
    ride_date = models.DateField()
    ride_time = models.TimeField()
    
    passengers_count = models.PositiveIntegerField()
    women_only = models.BooleanField(default=False)

    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Optional return trip
    is_return_ride = models.BooleanField(default=False)
    return_date = models.DateField(null=True, blank=True)
    return_time = models.TimeField(null=True, blank=True)
    return_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    return_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    passenger_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    def __str__(self):
        return f"Ride by {self.user.name} on {self.ride_date} from {self.from_location} to {self.to_location}"

# Each intermediate stop: C, D, etc.
class RideShareStop(models.Model):
    ride_booking = models.ForeignKey(RideShareBooking, on_delete=models.CASCADE, related_name='stops')
    stop_location = models.CharField(max_length=255)

    order = models.PositiveIntegerField(editable=False)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if self._state.adding and self.order is None:
            max_order = RideShareStop.objects.filter(ride_booking=self.ride_booking).aggregate(
                models.Max('order')
            )['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Stop {self.order}: {self.stop_location}"


# All possible segment combinations: A→C, A→D, C→D, etc.
class RideShareRouteSegment(models.Model):
    ride_booking = models.ForeignKey(RideShareBooking, on_delete=models.CASCADE, related_name='route_segments')
    from_stop = models.CharField(max_length=255)
    to_stop = models.CharField(max_length=255)

    distance_km = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.from_stop} → {self.to_stop} (₹{self.price})"