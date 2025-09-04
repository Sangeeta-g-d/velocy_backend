from django.db import models
from rider_part.models import RideRequest
from auth_api.models import CustomUser
from rider_part.models import DriverWalletTransaction
from django.utils import timezone

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

    def process(self):
        """Mark as processed and deduct from wallet"""
        if self.status != 'processed':
            self.status = 'processed'
            self.reviewed_at = timezone.now()
            self.save()

            # Deduct from wallet now
            DriverWalletTransaction.objects.create(
                driver=self.driver,
                amount=-self.amount,
                transaction_type="withdrawal",
                description=f"Cash out processed: {self.amount}"
            )
