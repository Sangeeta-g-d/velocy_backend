from django.db import models
from django.conf import settings
from django.utils import timezone
import pytz
from auth_api.models import CustomUser

class RentedVehicle(models.Model):
    FUEL_TYPE_CHOICES = (
        ('Petrol', 'Petrol'),
        ('Diesel', 'Diesel'),
        ('Electric', 'Electric'),
        ('Hybrid', 'Hybrid'),
    )

    TRANSMISSION_CHOICES = (
        ('Manual', 'Manual'),
        ('Automatic', 'Automatic'),
    )

    VEHICLE_TYPE_CHOICES = (
        ('SUV', 'SUV'),
        ('Hatchback', 'Hatchback'),
        ('Sedan', 'Sedan'),
    )

    vehicle_name = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=100, choices=VEHICLE_TYPE_CHOICES)  # ✅ updated with choices
    registration_number = models.CharField(max_length=20, unique=True)
    seating_capacity = models.PositiveIntegerField()
    bag_capacity = models.PositiveIntegerField(default=0)  # ✅ already added
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES)
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    rental_price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    available_from_date = models.DateField()
    available_to_date = models.DateField()
    pickup_location = models.CharField(max_length=255)
    security_deposite = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vehicle_papers_document = models.FileField(upload_to='vehicle_documents/')
    confirmation_checked = models.BooleanField(default=False)
    vehicle_color = models.CharField(max_length=30)
    is_ac = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='rented_vehicles')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vehicle_name} - {self.registration_number}"



class RentedVehicleImage(models.Model):
    vehicle = models.ForeignKey('RentedVehicle', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='vehicle_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.vehicle.vehicle_name} ({self.vehicle.registration_number})"


class RentedVehicleRating(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]  # 1 to 5

    vehicle = models.ForeignKey('RentedVehicle', on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vehicle_ratings')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vehicle', 'user')  # prevent duplicate ratings from same user
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vehicle.vehicle_name} - {self.rating}⭐ by {self.user.email}"
    


class RentalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('rejected','Rejected'),
        ('handovered','Handovered')
    )

    vehicle = models.ForeignKey(RentedVehicle, on_delete=models.CASCADE, related_name='rental_requests')
    lessor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_rental_requests')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_rental_requests')
    pickup_datetime = models.DateTimeField()
    dropoff_datetime = models.DateTimeField()
    license_document = models.FileField(upload_to='license_uploads/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    free_cancellation_deadline = models.DateTimeField(blank=True, null=True)

    # New fields
    duration_hours = models.PositiveIntegerField(default=1)
    total_rent_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        # Set lessor automatically if not provided
        if not self.lessor:
            self.lessor = self.vehicle.user

        # Set free cancellation deadline (24 hours before pickup in IST)
        if not self.free_cancellation_deadline:
            india_tz = pytz.timezone('Asia/Kolkata')
            pickup_ist = self.pickup_datetime.astimezone(india_tz)
            self.free_cancellation_deadline = pickup_ist - timezone.timedelta(hours=24)

        # Calculate rental duration in hours (rounding up any partial hour)
        duration_seconds = (self.dropoff_datetime - self.pickup_datetime).total_seconds()
        self.duration_hours = max(1, int((duration_seconds + 3599) // 3600))  # 3600 seconds = 1 hour

        # Calculate total rent price
        self.total_rent_price = self.vehicle.rental_price_per_hour * self.duration_hours

        super().save(*args, **kwargs)

    def can_cancel_for_free(self):
        india_tz = pytz.timezone('Asia/Kolkata')
        now_ist = timezone.now().astimezone(india_tz)
        return now_ist <= self.free_cancellation_deadline

    def __str__(self):
        return f"{self.user.username or self.user.phone_number} → {self.vehicle.vehicle_name} ({self.status})"

    
class HandoverChecklist(models.Model):
    rental_request = models.OneToOneField(RentalRequest, on_delete=models.CASCADE, related_name='handover_checklist')
    
    handed_over_car_keys = models.BooleanField(default=False)
    handed_over_vehicle_documents = models.BooleanField(default=False)
    fuel_tank_full = models.BooleanField(default=False)
    
    checklist_completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Handover for RentalRequest #{self.rental_request.id}"
