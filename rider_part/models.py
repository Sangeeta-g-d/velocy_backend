from django.db import models
from django.contrib.auth import get_user_model
from admin_part.models import City,VehicleType
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import uuid
from django.utils import timezone
from datetime import timedelta
from ride_sharing.models import RideJoinRequest

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
    RIDE_PURPOSE_CHOICES = (
    ('official', 'Official'),
    ('personal', 'Personal'),
    ('corporate_admin', 'Corporate Admin Booking'), 
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

    start_time = models.DateTimeField(null=True, blank=True, help_text="Ride start time (in IST)")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Ride end time (in IST)")
    
    driver = models.ForeignKey(User,on_delete=models.SET_NULL,null=True, blank=True, related_name='accepted_rides')
    company = models.ForeignKey('corporate_web.CompanyAccount', on_delete=models.SET_NULL, null=True, blank=True)
    ride_purpose = models.CharField(max_length=20,choices=RIDE_PURPOSE_CHOICES,default='personal',help_text="Whether this is a company-funded or personal ride")

    employees = models.ManyToManyField(User, blank=True, related_name='rides_as_passenger',
                                   help_text="Employees included in this corporate admin ride.")
    
    require_otp = models.BooleanField(default=True, help_text="Whether OTP is needed for this ride")

    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ride by {self.user} - {self.from_location} → {self.to_location}"
    
    @property
    def ride_amount(self):
        """
        Returns the offered price if available, 
        otherwise the estimated price.
        """
        return self.offered_price if self.offered_price is not None else self.estimated_price


class RideLocationSession(models.Model):
    ride = models.OneToOneField(
        "RideRequest",
        on_delete=models.CASCADE,
        related_name="location_session"
    )
    session_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True
    )
    expiry_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expiry_time


class RideLocationUpdate(models.Model):
    session = models.ForeignKey(
        RideLocationSession,
        on_delete=models.CASCADE,
        related_name="updates"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session.ride.id} → ({self.latitude}, {self.longitude})"


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
    
class RideOTP(models.Model):
    ride = models.OneToOneField(RideRequest, on_delete=models.CASCADE, related_name='otp')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)
    

class RidePaymentDetail(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('wallet','Wallet')
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    ride = models.OneToOneField('RideRequest', on_delete=models.CASCADE, related_name='payment_detail')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    promo_code = models.ForeignKey('admin_part.PromoCode', on_delete=models.SET_NULL, null=True, blank=True)
    promo_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    driver_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Actual amount driver will earn from this ride (before platform fees if applicable)")
    upi_payment_id = models.CharField(max_length=100, null=True, blank=True, help_text="Transaction ID for UPI payments")
    gst_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    def __str__(self):
        return f"Payment for Ride {self.ride.id} by {self.user}"
    

class DriverWalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('ride_earning', 'Ride Earning'),
        ('adjustment', 'Manual Adjustment'),
        ('withdrawal', 'Withdrawal'),
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty'),
        ('refund', 'Refund'),
        ('Car pooling', 'Car pooling'),
    ]

    driver = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'driver'})

    # Original ride FK (for RideRequest)
    ride = models.ForeignKey(RideRequest, on_delete=models.SET_NULL, null=True, blank=True)

    # ✅ New FK to RideShareBooking
    shared_join_ride = models.ForeignKey(RideJoinRequest, on_delete=models.SET_NULL, null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.driver} - {self.transaction_type} - {self.amount}"


class DriverPendingFee(models.Model):
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pending_fees")
    ride = models.ForeignKey(RideRequest, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    settled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Settled" if self.settled else "Pending"
        return f"{self.driver} - Ride {self.ride.id} - Fee {self.amount} ({status})"

class RideMessage(models.Model):
    ride = models.ForeignKey(RideRequest, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class RideReportSubmission(models.Model):
    ride = models.ForeignKey(
        RideRequest,
        on_delete=models.CASCADE,
        related_name='report_submissions',
        null=True, blank=True
    )
    ride_share_booking = models.ForeignKey(
        'ride_sharing.RideShareBooking',
        on_delete=models.CASCADE,
        related_name='report_submissions',
        null=True, blank=True
    )
    report_type = models.ForeignKey(
        'admin_part.RideReport',
        on_delete=models.CASCADE,
        related_name='report_submissions'
    )
    message = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.ride:
            return f"Report on Ride #{self.ride.id} - {self.report_type.report_name}"
        elif self.ride_share_booking:
            return f"Report on RideShare #{self.ride_share_booking.id} - {self.report_type.report_name}"
        return f"Report - {self.report_type.report_name}"



class FavoriteToLocation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_to_locations')
    name = models.CharField(max_length=100, help_text="Custom name for this location")
    to_location = models.CharField(max_length=255)
    to_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    to_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class EmergencyContact(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="emergency_contacts",
        help_text="Rider who owns this emergency contact"
    )
    name = models.CharField(max_length=100, help_text="Emergency contact person's name")
    phone = models.CharField(max_length=15, help_text="Emergency contact phone number")
    email = models.EmailField(blank=True, null=True, help_text="Emergency contact email (optional)")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone}) - for {self.user}"