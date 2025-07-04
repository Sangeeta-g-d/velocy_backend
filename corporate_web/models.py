from django.db import models
from auth_api.models import CustomUser
from django.utils import timezone
# Create your models here.

class CompanyAccount(models.Model):
    admin_user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='company_account')
    company_name = models.CharField(max_length=255)
    business_registration_number = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name


class EmployeeCredit(models.Model):
    employee = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='credit'
    )
    total_credits = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_credits = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True) 

    def available_credits(self):
        return self.total_credits - self.used_credits

    def __str__(self):
        return f"{self.employee.username} - {self.available_credits()} credits"

    def close_credits(self):
        self.is_active = False
        self.save()

    def reopen_credits(self):
        self.is_active = True
        self.save()