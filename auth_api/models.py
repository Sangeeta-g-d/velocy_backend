from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import datetime
from datetime import timedelta
from django.core.validators import MinValueValidator, MaxValueValidator

class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number must be set')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(phone_number, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('rider', 'Rider'),
        ('driver', 'Driver'),
        ('corporate_admin', 'Corporate_Admin'),
        ('employee','Employee')
    )

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    DRIVER_TYPE_CHOICES = (
        ('normal', 'Normal Only'),
        ('corporate', 'Corporate Only'),
        ('both', 'Both'),
    )

    phone_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES,default='rider')
    username = models.CharField(max_length=100, blank=True, null=True)
    profile = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    area = models.CharField(max_length=255, blank=True, null=True)
    aadhar_card = models.FileField(upload_to='aadhar_cards/', blank=True, null=True)
    address_type = models.CharField(max_length=10, blank=True, null=True)
    cash_payments_left = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=False)

    company = models.ForeignKey('corporate_web.CompanyAccount', on_delete=models.SET_NULL,null=True,blank=True,related_name='employees')


    # corporate settings
    driver_type = models.CharField(max_length=20,choices=DRIVER_TYPE_CHOICES,blank=True,null=True,
        help_text="Defines if the driver can do normal, corporate or both rides",default="normal"
    )
    is_universal_corporate_driver = models.BooleanField(default=False,
        help_text="Check this if driver can serve all corporate accounts"
    )
    is_corporate_driver = models.BooleanField(default=False)
    corporate_companies = models.ManyToManyField('corporate_web.CompanyAccount',
        blank=True,
        related_name='assigned_drivers',
        help_text="If not universal, assign specific corporate accounts"
    )

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.phone_number


class UserFCMToken(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="fcm_tokens"
    )
    token = models.TextField(unique=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)  # optional (android/ios/web)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.phone_number} - {self.token[:20]}..."


class PhoneOTP(models.Model):
    phone_number = models.CharField(max_length=15, unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=2)



class DriverVehicleInfo(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='vehicle_info')

    vehicle_number = models.CharField(max_length=20)
    vehicle_type = models.ForeignKey(
        "admin_part.VehicleType", 
        on_delete=models.CASCADE, 
        related_name="drivers",
        default=2  # temporary default id for migration
    )
    year = models.PositiveIntegerField()
    car_company = models.CharField(max_length=50)
    car_model = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.user.phone_number} - {self.vehicle_number}"
    
    
class DriverDocumentInfo(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='document_info')
    license_plate_number = models.CharField(max_length=20)
    vehicle_registration_doc = models.FileField(upload_to='driver_docs/vehicle_registration/')
    driver_license = models.FileField(upload_to='driver_docs/license/')
    vehicle_insurance = models.FileField(upload_to='driver_docs/insurance/')
    verified = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.user.phone_number} - License Plate: {self.license_plate_number}"


class DriverRating(models.Model):
    ride_request = models.ForeignKey('rider_part.RideRequest', on_delete=models.CASCADE, related_name='driver_ratings',null=True, blank=True)
    driver = models.ForeignKey('auth_api.CustomUser', on_delete=models.CASCADE, related_name='received_ratings', limit_choices_to={'role': 'driver'})
    ride_sharing = models.ForeignKey('ride_sharing.RideJoinRequest', on_delete=models.CASCADE, related_name='driver_ratings', null=True, blank=True)
    rated_by = models.ForeignKey('auth_api.CustomUser', on_delete=models.CASCADE, related_name='given_ratings', limit_choices_to={'role': 'rider'})
    rating = models.DecimalField(max_digits=2, decimal_places=1, validators=[MinValueValidator(1.0), MaxValueValidator(5.0)])
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ride_request', 'driver')

    def __str__(self):
        return f"{self.rated_by} rated {self.driver} - {self.rating}/5"