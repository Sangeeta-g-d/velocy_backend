from django.db import models
from django.utils import timezone
from auth_api.models import CustomUser
from django.utils import timezone
import pytz
# Create your models here.

class City(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class VehicleType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    number_of_passengers = models.PositiveIntegerField(
        help_text="Maximum number of passengers allowed", default=1
    )
    image = models.ImageField(
        upload_to='vehicle_types/',
        blank=True,
        null=True,
        help_text="Upload an image representing this vehicle type"
    )

    def __str__(self):
        return f"{self.name} ({self.number_of_passengers} passengers)"
    
class CityVehiclePrice(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='vehicle_prices')
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE, related_name='city_prices')
    price_per_km = models.DecimalField(max_digits=6, decimal_places=2)  # ₹/km

    class Meta:
        unique_together = ('city', 'vehicle_type')  # Avoid duplicates

    def __str__(self):
        return f"{self.city.name} - {self.vehicle_type.name}: ₹{self.price_per_km}/km"


class PromoCode(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('flat', 'Flat'),
        ('percent', 'Percentage'),
    ]

    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=5, decimal_places=2, help_text="₹ for flat, % for percentage")
    max_discount_amount = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Applicable only for percentage discount")
    min_ride_amount = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    usage_limit_per_user = models.PositiveIntegerField(default=1)
    total_usage_limit = models.PositiveIntegerField(null=True, blank=True)  # None = unlimited
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        now = timezone.now()
        return self.valid_from <= now <= self.valid_to

    def is_valid(self, user, ride_amount):
        now = timezone.now()

        if not self.is_active:
            return False

        if ride_amount < self.min_ride_amount:
            return False

        from .models import PromoCodeUsage
        user_usage_count = PromoCodeUsage.objects.filter(user=user, promo_code=self).count()
        if user_usage_count >= self.usage_limit_per_user:
            return False

        if self.total_usage_limit is not None:
            total_usage = PromoCodeUsage.objects.filter(promo_code=self).count()
            if total_usage >= self.total_usage_limit:
                return False

        return True

    def __str__(self):
        return self.code


class PromoCodeUsage(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE)
    ride = models.ForeignKey('rider_part.RideRequest', on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'promo_code', 'ride')


class PlatformSetting(models.Model):
    PLATFORM_FEE_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('flat', 'Flat'),
    )

    fee_type = models.CharField(max_length=10, choices=PLATFORM_FEE_TYPE_CHOICES, default='percentage')
    fee_value = models.DecimalField(max_digits=5, decimal_places=2, help_text="Fee percentage or flat amount")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.fee_value} ({self.fee_type})"
    
class PrepaidPlan(models.Model):
    PLAN_VALIDITY_CHOICES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half-Yearly'),
        ('yearly', 'Yearly'),
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    validity_type = models.CharField(max_length=20, choices=PLAN_VALIDITY_CHOICES)
    validity_days = models.PositiveIntegerField()
    credits_provided = models.PositiveIntegerField(help_text="Credits given when the plan is purchased.")
    is_active = models.BooleanField(default=True)
    benefits = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - ₹{self.price} ({self.credits_provided} credits)"


class RideReport(models.Model):
    report_name = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.report_name