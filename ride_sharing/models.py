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
    min_price_per_km = models.DecimalField(max_digits=10, decimal_places=2)
    max_price_per_km = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"₹{self.min_price_per_km} – ₹{self.max_price_per_km} per km"


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
    to_location_estimated_arrival_time = models.TimeField(null=True, blank=True)
    
    passengers_count = models.PositiveIntegerField()
    women_only = models.BooleanField(default=False)
    seats_remaining = models.PositiveIntegerField(null=True, blank=True)

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
    stop_lat = models.FloatField(null=True, blank=True)
    stop_lng = models.FloatField(null=True, blank=True)

    order = models.PositiveIntegerField(editable=False)
    estimated_arrival_time = models.TimeField(null=True, blank=True)  # ⏱️ new field

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


class RideJoinRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    ride = models.ForeignKey('RideShareBooking', on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_join_requests')

    # Optional if joining a direct ride (full ride from A to B)
    segment = models.ForeignKey(
        'RideShareRouteSegment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='join_requests'
        )


    seats_requested = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, help_text="Optional message from the passenger.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['ride', 'user', 'segment']
        ordering = ['-created_at']

    def __str__(self):
        if self.segment:
            return f"{self.user.username} → Ride {self.ride.id} [{self.segment.from_stop} → {self.segment.to_stop}]"
        return f"{self.user.username} → Ride {self.ride.id} (Direct Ride)"
