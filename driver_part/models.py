from django.db import models
from rider_part.models import RideRequest
from auth_api.models import CustomUser
from rider_part.models import DriverWalletTransaction
from django.utils import timezone
from django.db.models import Sum
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
        ('rejected', 'Rejected'),
    ]

    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'driver'})
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='processed_cash_outs')

    def process(self, reviewed_by=None):
        """Mark as processed and deduct from wallet"""
        if self.status != 'processed':
            # Check if driver has sufficient balance
            available_balance = DriverWalletTransaction.objects.filter(
                driver=self.driver
            ).exclude(
                description__icontains="Cash payment for Ride"
            ).aggregate(total=Sum('amount'))['total'] or 0.0
            
            if float(self.amount) > float(available_balance):
                raise ValueError("Insufficient balance for withdrawal")
            
            self.status = 'processed'
            self.reviewed_at = timezone.now()
            if reviewed_by:
                self.reviewed_by = reviewed_by
            self.save()

            # Deduct from wallet now
            DriverWalletTransaction.objects.create(
                driver=self.driver,
                amount=-self.amount,
                transaction_type="withdrawal",
                description=f"Cash out processed: {self.amount}"
            )

    def reject(self, reviewed_by=None):
        """Mark as rejected without deducting from wallet"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.reviewed_at = timezone.now()
            if reviewed_by:
                self.reviewed_by = reviewed_by
            self.save()

    def __str__(self):
        return f"{self.driver} - {self.amount} - {self.status}"