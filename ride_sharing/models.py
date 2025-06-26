from django.db import models
from auth_api.models import CustomUser
# Create your models here.

class RideShareVehicle(models.Model):
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ride_vehicles')
    vehicle_number = models.CharField(max_length=20)
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

class Ride(models.Model):
    vehicle = models.ForeignKey(RideShareVehicle, on_delete=models.CASCADE, related_name='rides')
    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='shared_rides')
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    ride_date = models.DateField()
    ride_time = models.TimeField()
    total_seats = models.PositiveIntegerField(default=0)  # Total fixed at creation
    seats_left = models.PositiveIntegerField()   # This will decrease as users join

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.from_location} to {self.to_location} on {self.ride_date}"


class RideJoinRequest(models.Model):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ride_join_requests')
    seats_requested = models.PositiveIntegerField(default=1)
    status_choices = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name} -> {self.ride} [{self.status}]"
