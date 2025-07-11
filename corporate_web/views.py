from django.shortcuts import render,redirect,get_object_or_404
from . models import *
from django.contrib.auth.hashers import make_password
from django.db import transaction, IntegrityError
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth import get_user_model
from django.utils.timezone import localtime
import pytz
from django.utils.timezone import make_aware

from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from . models import *
from django.urls import reverse
from django.template.loader import render_to_string
import razorpay
from rider_part.models import RideRequest
from django.db.models import Sum
from django.conf import settings
from django.http import JsonResponse
User = get_user_model()
# Create your views here.


def register(request):
    if request.method == "POST":
        # Get admin data
        admin_name = request.POST.get("admin_name")
        phone_number = request.POST.get("phone_number")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Get company data
        company_name = request.POST.get("company_name")
        registration_number = request.POST.get("registration_number")
        gst_number = request.POST.get("gst_number")
        address = request.POST.get("address")
        city = request.POST.get("city")
        pincode = request.POST.get("pincode")

        # Create admin user
        admin_user = CustomUser.objects.create(
            username=admin_name,
            phone_number=phone_number,
            email=email,
            password=make_password(password),
            role="corporate_admin",
            is_active=True
        )

        # Create company
        CompanyAccount.objects.create(
            admin_user=admin_user,
            company_name=company_name,
            business_registration_number=registration_number,
            gst_number=gst_number,
            address=address,
            city=city,
            pincode=pincode,
            is_approved=False
        )

        # Set toast message in session
        request.session["toast_message"] = "Registration successful. Please wait for admin approval."
        request.session["toast_type"] = "success"

        return redirect("register")  # Use your URL name here

    # Pop toast message so it doesn't persist on reload
    toast_message = request.session.pop("toast_message", "")
    toast_type = request.session.pop("toast_type", "success")

    return render(request, "register.html", {
        "toast_message": toast_message,
        "toast_type": toast_type
    })


def plans(request):
    plans = PrepaidPlan.objects.filter(is_active=True).order_by('price')
    return render(request, 'plans.html', {'plans': plans})

@login_required(login_url='/login/')
def create_razorpay_order(request, plan_id):
    if request.method != "POST":
        print("❌ Invalid request method for create_razorpay_order.")
        return HttpResponseForbidden("Invalid request method")

    try:
        plan = PrepaidPlan.objects.get(id=plan_id)
        print(f"🔎 Selected Plan: {plan.name}, Price: {plan.price}, Validity: {plan.validity_days} days")

        amount_in_paisa = int(plan.price * 100)
        print(f"💰 Amount in paisa: {amount_in_paisa}")

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        payment = client.order.create({
            'amount': amount_in_paisa,
            'currency': 'INR',
            'payment_capture': '1'
        })

        print(f"🧾 Razorpay Order Created: {payment['id']}")

        prepaid = CompanyPrepaidPlan.objects.create(
            company=request.user.company_account,
            plan=plan,
            razorpay_order_id=payment['id'],
            amount_paid=plan.price
        )

        print(f"✅ CompanyPrepaidPlan created: ID {prepaid.id}, Order ID: {prepaid.razorpay_order_id}")

        return JsonResponse({
            'order_id': payment['id'],
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'amount': amount_in_paisa,
            'currency': 'INR',
            'company_prepaid_id': prepaid.id
        })

    except Exception as e:
        print("❌ Exception in create_razorpay_order:", e)
        return JsonResponse({'error': 'Failed to create Razorpay order'}, status=500)


@csrf_exempt
def payment_success(request):
    if request.method == "POST":
        data = request.POST
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")

        print("📥 Payment POST data received")
        print(f"  - Order ID: {razorpay_order_id}")
        print(f"  - Payment ID: {razorpay_payment_id}")
        print(f"  - Signature: {razorpay_signature}")

        try:
            plan = CompanyPrepaidPlan.objects.select_related('company', 'plan').get(
                razorpay_order_id=razorpay_order_id
            )

            print(f"🔁 Found CompanyPrepaidPlan for order {razorpay_order_id}")
            print(f"  - Company: {plan.company.company_name}")
            print(f"  - Plan: {plan.plan.name}")

            plan.razorpay_payment_id = razorpay_payment_id
            plan.razorpay_signature = razorpay_signature
            plan.payment_status = 'success'

            # Use purchase_date as start_date
            plan.start_date = plan.purchase_date
            plan.end_date = plan.purchase_date + timezone.timedelta(days=plan.plan.validity_days)
            plan.credits_remaining = plan.plan.credits_provided
            plan.total_credits = plan.plan.credits_provided

            plan.save()
            print("✅ Plan updated successfully")

            company = plan.company
            company.purchased_plan = True
            company.save()
            print("🏢 Company updated with purchased_plan=True")

            return redirect('/corporate/success_page')

        except CompanyPrepaidPlan.DoesNotExist:
            print("❌ CompanyPrepaidPlan not found for Razorpay Order ID:", razorpay_order_id)
            return redirect('/plans/?status=fail')

def success_page(request):
    return render(request,'success_page.html')

@login_required(login_url='/login/')
def company_dashboard(request):
    user = request.user
    active_plan = None
    assigned_credits = 0
    available_to_assign = 0
    used_credits = 0
    remaining_plan_credits = 0

    if hasattr(user, 'company_account'):
        company = user.company_account

        active_plan = CompanyPrepaidPlan.objects.filter(
            company=company, payment_status='success'
        ).order_by('-start_date').first()

        if active_plan:
            # Get assigned and used credits
            assigned_credits = EmployeeCredit.objects.filter(
                employee__company=company
            ).aggregate(total=Sum('total_credits'))['total'] or 0

            used_credits = EmployeeCredit.objects.filter(
                employee__company=company
            ).aggregate(total=Sum('used_credits'))['total'] or 0

            available_to_assign = max(active_plan.total_credits - assigned_credits, 0)
            remaining_plan_credits = max(active_plan.total_credits - used_credits, 0)

    context = {
        "current_url_name": "company_dashboard",
        "active_plan": active_plan,
        "assigned_credits": assigned_credits,
        "available_to_assign": available_to_assign,
        "remaining_plan_credits": remaining_plan_credits,
    }
    return render(request, 'company_dashboard.html', context)

@login_required(login_url='/login/')
def add_employee(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        raw_phone = request.POST.get('phone_number')
        phone_number = f"+91{raw_phone.strip()}" if not raw_phone.startswith('+91') else raw_phone.strip()
        email = request.POST.get('email')
        gender = request.POST.get('gender')
        street = request.POST.get('street')
        area = request.POST.get('area')
        profile = request.FILES.get('profile')
        total_credits = request.POST.get('total_credits')

        if not total_credits:
            return redirect('/corporate/add_employee/?error=Total credit is required.')

        try:
            total_credits = float(total_credits)
        except ValueError:
            return redirect('/corporate/add_employee/?error=Invalid credit amount.')

        if User.objects.filter(phone_number=phone_number).exists():
            return redirect('/corporate/add_employee/?error=Phone number already registered.')

        try:
            company = request.user.company_account
            active_plan = CompanyPrepaidPlan.objects.filter(
                company=company, payment_status='success'
            ).order_by('-purchase_date').first()

            if not active_plan:
                return redirect('/corporate/add_employee/?error=No active plan found.')

            assigned_credits = EmployeeCredit.objects.filter(
                employee__company_account=company
            ).aggregate(Sum('total_credits'))['total_credits__sum'] or 0

            unassigned_credits = active_plan.total_credits - assigned_credits

            if total_credits > unassigned_credits:
                return redirect(f'/corporate/add_employee/?error=Not enough available company credits. Only {unassigned_credits} left.')

            with transaction.atomic():
                employee = User.objects.create(
                    username=username,
                    phone_number=phone_number,
                    email=email,
                    gender=gender,
                    street=street,
                    area=area,
                    profile=profile,
                    role='employee',
                    company=company,
                )

                EmployeeCredit.objects.create(
                    employee=employee,
                    total_credits=total_credits,
                    used_credits=0,
                    is_active=True
                )

            return redirect('/corporate/add_employee/?created=1')

        except Exception as e:
            return redirect(f'/corporate/add_employee/?error={str(e)}')

    # GET request
    available_to_assign = 0
    if hasattr(request.user, 'company_account'):
        company = request.user.company_account
        active_plan = CompanyPrepaidPlan.objects.filter(
            company=company, payment_status='success'
        ).order_by('-purchase_date').first()
        if active_plan:
            assigned = EmployeeCredit.objects.filter(
                employee__company_account=company
            ).aggregate(Sum('total_credits'))['total_credits__sum'] or 0
            available_to_assign = max(active_plan.total_credits - assigned, 0)

    context = {
        "current_url_name": "company_dashboard",
        "available_to_assign": available_to_assign
    }
    return render(request, 'add_employee.html', context)


def edit_employee_view(request, employee_id):
    employee = get_object_or_404(CustomUser, id=employee_id, role='employee')
    if request.method == 'POST':
        employee.username = request.POST.get('username')
        employee.phone_number = request.POST.get('phone_number')
        employee.email = request.POST.get('email')
        employee.gender = request.POST.get('gender')
        employee.street = request.POST.get('street')
        employee.area = request.POST.get('area')

        if request.FILES.get('profile'):
            employee.profile = request.FILES['profile']

        # Update credits if changed
        try:
            credit = float(request.POST.get('total_credits'))
            employee.cash_payments_left = credit
        except:
            pass

        employee.save()
        return redirect(reverse('employee_list') + '?updated=1')

    return render(request, 'edit_employee.html', {'employee': employee})



@login_required
def employee_list(request):
    if hasattr(request.user, 'company_account'):
        employees = CustomUser.objects.filter(
            role='employee',
            company=request.user.company_account
        )
    else:
        employees = []

    context = {
        "employees": employees,
        "current_url_name": "employee_list"
    }
    return render(request, 'employee_list.html', context)

def employee_details(request, employee_id):
    employee = get_object_or_404(CustomUser, id=employee_id, role='employee')

    context = {
        "employee": employee,
        "credit": getattr(employee, 'credit', None),  # Optional, avoid error if not created
        "current_url_name": "employee_list"
    }
    return render(request, 'employee_details.html', context)


@login_required(login_url='/login/')
def book_ride(request):
    context= {
        "current_url_name": "book_ride"
    }
    return render(request, 'book_ride.html', context)
        
def employee_activity(request, employee_id):
    employee = get_object_or_404(CustomUser, id=employee_id)

    # Get recent 20 rides
    rides = RideRequest.objects.filter(user=employee).order_by('-created_at')[:20]

    # Convert UTC to IST
    ist = pytz.timezone("Asia/Kolkata")
    for ride in rides:
        utc_time = ride.created_at
        if utc_time.tzinfo is None:
            utc_time = make_aware(utc_time, timezone=pytz.UTC)
        ride.created_at_ist = utc_time.astimezone(ist)

    context = {
        "employee_id": employee_id,
        "employee": employee,
        "recent_rides": rides,
        "current_url_name": "employee_activity"
    }
    return render(request, 'employee_activity.html', context)