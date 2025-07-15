from django.core.management.base import BaseCommand
from django.utils import timezone
from corporate_web.models import CompanyPrepaidPlan


class Command(BaseCommand):
    help = 'Expire corporate plans and reclaim unused employee credits to company unassigned credits'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        expired_plans = CompanyPrepaidPlan.objects.filter(end_date__lt=now, payment_status='success')

        for plan in expired_plans:
            company = plan.company
            if not company:
                self.stdout.write(self.style.WARNING(f"Skipped a plan with no company assigned (Plan ID: {plan.id})"))
                continue
            
            total_reclaimed = plan.reclaim_employee_credits()
            self.stdout.write(
                self.style.SUCCESS(
                    f"{company.company_name}: Plan expired and ₹{total_reclaimed:.2f} credits reclaimed."
                )
            )

