from django.db import models
from django.utils import timezone
from django.db.models import Sum
from auth_api.models import CustomUser
from admin_part.models import PrepaidPlan


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


class CompanyPrepaidPlan(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )

    company = models.ForeignKey(CompanyAccount, on_delete=models.SET_NULL, null=True)
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
    total_credits = models.PositiveIntegerField(default=0)
    credits_spent_by_employees = models.PositiveIntegerField(default=0)
    credits_spent_by_company = models.PositiveIntegerField(default=0)

    def is_active(self):
        return self.start_date and self.end_date and self.start_date <= timezone.now() <= self.end_date

    @property
    def assigned_credits(self):
        return EmployeeCredit.objects.filter(
            employee__company=self.company,
            is_active=True
        ).aggregate(total=Sum('total_credits'))['total'] or 0

    @property
    def unassigned_credits(self):
        """Credits available to company (not assigned to employees)"""
        return max(self.total_credits - self.assigned_credits, 0)

    @property
    def plan_credits_remaining(self):
        """Total remaining credits (employees + company)"""
        return max(self.total_credits - self.total_credits_spent, 0)

    @property
    def total_credits_spent(self):
        return self.credits_spent_by_employees + self.credits_spent_by_company

    def spend_company_credits(self, amount):
        """Called when company books a ride using unassigned credits"""
        if self.unassigned_credits >= amount:
            self.credits_spent_by_company += amount
            self.save()
        else:
            raise ValueError("Not enough company credits available.")

    def reclaim_employee_credits(self):
        """Move remaining employee credits back to unassigned pool on expiry"""
        total_reclaimed = 0
        total_used = 0
        employee_credits = EmployeeCredit.objects.filter(
            employee__company=self.company,
            is_active=True
        )

        for credit in employee_credits:
            remaining = credit.available_credits()
            if remaining > 0:
                total_reclaimed += int(remaining)

            total_used += int(credit.used_credits)

            # Keep only used credits, reclaim rest
            credit.total_credits = credit.used_credits
            credit.is_active = False
            credit.save()

        # 🛠️ Update employee spent field to preserve accurate remaining credits
        self.credits_spent_by_employees = total_used
        self.save()

        return total_reclaimed

    def __str__(self):
        return f"{self.company.company_name} - {self.plan.name} ({self.payment_status})"
