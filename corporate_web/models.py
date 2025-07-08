from django.db import models
from auth_api.models import CustomUser
from django.utils import timezone
from admin_part.models import PrepaidPlan
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
    purchased_plan = models.BooleanField(default=False)
    def __str__(self):
        return self.company_name


class CompanyPrepaidPlan(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )

    company = models.ForeignKey('corporate_web.CompanyAccount', on_delete=models.CASCADE, related_name='purchased_plans')
    plan = models.ForeignKey(PrepaidPlan, on_delete=models.CASCADE, related_name='company_subscriptions')
    purchase_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Credit tracking
    credits_remaining = models.PositiveIntegerField(default=0)

    def is_active(self):
        return self.start_date and self.end_date and self.start_date <= timezone.now() <= self.end_date

    def __str__(self):
        return f"{self.company.company_name} - {self.plan.name} ({self.payment_status})"



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