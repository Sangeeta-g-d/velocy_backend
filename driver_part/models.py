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


class CashOutRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
    ]

    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'driver'})
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.driver.phone_number} requested ₹{self.amount} - {self.status}"
