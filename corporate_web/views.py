from django.shortcuts import render,redirect,get_object_or_404
from . models import *
from django.contrib.auth.hashers import make_password
from django.db import transaction, IntegrityError
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from . models import *
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


def company_dashboard(request):
    context = {
        "current_url_name":"company_dashboard"
    }
    return render(request,'company_dashboard.html',context)

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

        if User.objects.filter(phone_number=phone_number).exists():
            return redirect('/corporate/add_employee/?error=Phone number already registered.')

        try:
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
                    company=request.user.company_account,
                )

                EmployeeCredit.objects.create(
                    employee=employee,
                    total_credits=total_credits or 0,
                    used_credits=0,
                    is_active=True
                )

            return redirect('/corporate/add_employee/?created=1')

        except Exception as e:
            return redirect(f'/corporate/add_employee/?error={str(e)}')

    context = {
        "current_url_name": "company_dashboard"
    }
    return render(request, 'add_employee.html', context)


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