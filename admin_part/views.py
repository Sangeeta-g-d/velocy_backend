from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import authenticate, login,logout
from auth_api.models import CustomUser,DriverDocumentInfo
from .models import *
from driver_part.models import CashOutRequest
import json
import os
from django.contrib import messages
from django.http import HttpResponseRedirect

from django.conf import settings
from django.http import JsonResponse
import json
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils.timezone import localtime
from auth_api.models import DriverRating
from django.utils.timezone import localtime
from corporate_web.models import CompanyAccount
from django.db.models import Avg
from rider_part.models import RideRequest, DriverWalletTransaction,RideReportSubmission
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from rent_vehicle.models import RentedVehicle,RentedVehicleImage
from django.utils.dateparse import parse_datetime
from urllib.parse import quote
from ride_sharing.models import RideShareVehicle
from decimal import Decimal
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
# Create your views here.

def dashboard(request):
    context = {
        "current_url_name":"dashboard"
    }
    return render(request,'dashboard.html',context)

def login_view(request):
    error = None

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        password = request.POST.get('password')

        user = authenticate(request, phone_number=phone_number, password=password)

        if user is not None:
            login(request, user)  # ✅ Log in first

            if user.is_superuser:
                return redirect('dashboard')  # Django admin or custom admin dashboard

            if user.role == 'corporate_admin':
                try:
                    company = CompanyAccount.objects.get(admin_user=user)
                    if not company.is_approved:
                        error = 'Your company is not yet verified. Please wait for approval.'
                    elif company.purchased_plan:  # check if any plans are purchased
                        return redirect('/corporate/company_dashboard')  # Main company dashboard
                    else:
                        return redirect('/corporate/choose_plan/')  # Redirect to buy plan
                except CompanyAccount.DoesNotExist:
                    error = 'Company account not found.'
            else:
                error = 'Access denied. Only approved company admins or superusers can log in.'
        else:
            error = 'Invalid phone number or password.'

    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('/login/')

def approve_drivers(request):
    drivers = CustomUser.objects.filter(role="driver")
    context = {
        "current_url_name":"approve_drivers",
        'drivers': drivers
    }
    return render(request, 'approve_drivers.html', context)

def users_list(request):
    riders = CustomUser.objects.filter(role="rider")
    context = {
        "current_url_name":"rider_list",
        'riders': riders
    }
    return render(request, 'users_list.html', context)

def driver_details(request, driver_id):
    driver = get_object_or_404(CustomUser, id=driver_id, role='driver')
    vehicle_info = getattr(driver, 'vehicle_info', None)
    document_info = getattr(driver, 'document_info', None)

    # ✅ Fetch approved companies
    approved_companies = CompanyAccount.objects.filter(is_approved=True)

    return render(request, 'driver_details.html', {
        'driver': driver,
        'vehicle_info': vehicle_info,
        'document_info': document_info,
        'companies': approved_companies,  # <-- pass this to template
        'current_url_name': 'approve_drivers',
    })

@login_required
def change_driver_role(request, driver_id):
    driver = get_object_or_404(CustomUser, id=driver_id, role='driver')

    if request.method == 'POST':
        driver_type = request.POST.get('driver_type')
        print("Driver Type:", driver_type)  # Debugging line

        if driver_type == 'normal':
            driver.driver_type = 'normal'
            driver.is_corporate_driver = False
            driver.is_universal_corporate_driver = False
            driver.corporate_companies.clear()

        elif driver_type == 'corporate_specific':
            driver.driver_type = 'corporate'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = False
            selected_ids = request.POST.getlist('company_ids')
            companies = CompanyAccount.objects.filter(id__in=selected_ids)
            driver.corporate_companies.set(companies)

        elif driver_type == 'corporate_universal':
            driver.driver_type = 'corporate'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = True
            driver.corporate_companies.clear()

        elif driver_type == 'both_specific':
            driver.driver_type = 'both'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = False
            selected_ids = request.POST.getlist('company_ids')
            companies = CompanyAccount.objects.filter(id__in=selected_ids)
            driver.corporate_companies.set(companies)

        elif driver_type == 'both_universal':
            driver.driver_type = 'both'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = True
            driver.corporate_companies.clear()

        driver.save()
        return redirect('driver_details', driver_id=driver.id)

    return redirect('approve_drivers')  # Fallback in case of non-POST request

@login_required
@require_POST
def update_driver_role(request, driver_id):
    driver = get_object_or_404(CustomUser, id=driver_id)
    
    if request.method == 'POST':
        role_type = request.POST.get('driver_type')
        company_ids = request.POST.getlist('company_ids')

        # Reset everything
        driver.is_corporate_driver = False
        driver.is_universal_corporate_driver = False
        driver.corporate_companies.clear()

        if role_type == 'normal':
            driver.driver_type = 'normal'

        elif role_type == 'corporate_specific':
            driver.driver_type = 'corporate'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = False
            driver.corporate_companies.set(company_ids)

        elif role_type == 'corporate_universal':
            driver.driver_type = 'corporate'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = True

        elif role_type == 'both_specific':
            driver.driver_type = 'both'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = False
            driver.corporate_companies.set(company_ids)

        elif role_type == 'both_universal':
            driver.driver_type = 'both'
            driver.is_corporate_driver = True
            driver.is_universal_corporate_driver = True

        driver.save()
        # messages.success(request, "Driver role updated successfully.")
        return redirect('driver_details', driver_id=driver_id)


def verify_driver(request, driver_id):
    if request.method == "POST":
        try:
            doc_info = DriverDocumentInfo.objects.get(user_id=driver_id)
            doc_info.verified = True
            doc_info.save()

            # Set cash payments left to 5 only if user is a driver
            user = doc_info.user
            if user.role == 'driver':
                user.cash_payments_left = 5
                user.save()

            return JsonResponse({"status": "success"})
        except DriverDocumentInfo.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Document not found"}, status=404)
        

def verify_rental_vehicle(request, vehicle_id):
    if request.method == "POST":
        try:
            vehicle_info = RentedVehicle.objects.get(id=vehicle_id)
            vehicle_info.is_approved = True
            vehicle_info.save()
            return JsonResponse({"status": "success"})
        except DriverDocumentInfo.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Document not found"}, status=404)
        
def disapprove_rental_vehicle(request, vehicle_id):
    if request.method == "POST":
        try:
            vehicle_info = RentedVehicle.objects.get(id=vehicle_id)
            vehicle_info.is_approved = False
            vehicle_info.save()
            return JsonResponse({"status": "success"})
        except DriverDocumentInfo.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Document not found"}, status=404)

        
def block_driver(request, driver_id):
    if request.method == "POST":
        try:
            user = CustomUser.objects.get(id=driver_id)
            user.is_active = False  # Blocking the user
            user.save()
            return JsonResponse({"status": "success"})
        except CustomUser.DoesNotExist:
            return JsonResponse({"status": "error", "message": "User not found"}, status=404)

def get_indian_cities(request):
    try:
        # Load from static file
        file_path = os.path.join(settings.STATIC_ROOT, 'indian_cities.json')
        with open(file_path, 'r') as f:
            cities = json.load(f)
        return JsonResponse({'cities': cities})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def add_city(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get("name")
            if not name:
                return JsonResponse({'success': False, 'error': 'City name is required.'})

            city, created = City.objects.get_or_create(name=name)
            if not created:
                return JsonResponse({'success': False, 'error': 'City already exists.'})
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})

@require_http_methods(["POST"])
@csrf_exempt  # Optional if CSRF token is passed via JS
def add_vehicle_type(request):
    try:
        name = request.POST.get("name")
        number = request.POST.get("number_of_passengers")
        image = request.FILES.get("image")

        if not name or not number:
            return JsonResponse({'success': False, 'error': 'All required fields must be filled.'})

        number = int(number)
        if number <= 0:
            return JsonResponse({'success': False, 'error': 'Passenger count must be at least 1.'})

        if VehicleType.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'error': 'Vehicle type already exists.'})

        VehicleType.objects.create(
            name=name,
            number_of_passengers=number,
            image=image
        )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
def fare_management(request):
    vehicle_types = VehicleType.objects.all()
    cities = City.objects.all()
    context = {
        'vehicle_types':vehicle_types,'cities':cities,'current_url_name':'cab'
    }
    return render(request,'fare_management.html',context)

def cab_management(request):
    cities = City.objects.all()
    vehicle_types = VehicleType.objects.all()
    city_vehicle_prices = CityVehiclePrice.objects.select_related('city', 'vehicle_type').all()

    return render(request, 'cab_management.html', {
        'cities': cities,
        'vehicle_types': vehicle_types,
        'city_vehicle_prices': city_vehicle_prices,
        'current_url_name':"cab"
    })


@csrf_exempt
def get_vehicle_type(request, pk):
    if request.method == "GET":
        try:
            vehicle = VehicleType.objects.get(pk=pk)
            data = {
                "id": vehicle.id,
                "name": vehicle.name,
                "number_of_passengers": vehicle.number_of_passengers,
                "image_url": vehicle.image.url if vehicle.image else "",
            }
            return JsonResponse(data)
        except VehicleType.DoesNotExist:
            return JsonResponse({"error": "Vehicle type not found"}, status=404)



@csrf_exempt
def update_vehicle_type(request, pk):
    if request.method == "POST":
        try:
            vehicle = VehicleType.objects.get(pk=pk)
            name = request.POST.get("name")
            passengers = request.POST.get("number_of_passengers")
            image = request.FILES.get("image")

            vehicle.name = name
            vehicle.number_of_passengers = passengers
            if image:
                vehicle.image = image
            vehicle.save()

            return JsonResponse({"success": True})
        except VehicleType.DoesNotExist:
            return JsonResponse({"error": "Vehicle type not found"}, status=404)
        
@csrf_exempt
def delete_city(request, pk):
    if request.method == "POST":
        try:
            city = City.objects.get(pk=pk)
            city.delete()
            return JsonResponse({"success": True})
        except City.DoesNotExist:
            return JsonResponse({"error": "City not found"}, status=404)
        

@csrf_exempt
def delete_vehicle_price(request, pk):
    if request.method == "POST":
        try:
            vehiclePrice = CityVehiclePrice.objects.get(pk=pk)
            vehiclePrice.delete()
            return JsonResponse({"success": True})
        except vehiclePrice.DoesNotExist:
            return JsonResponse({"error": "City not found"}, status=404)

        
@csrf_exempt
def delete_vehicle(request, pk):
    if request.method == "POST":
        try:
            vehicle = VehicleType.objects.get(pk=pk)
            vehicle.delete()
            return JsonResponse({"success": True})
        except VehicleType.DoesNotExist:
            return JsonResponse({"error": "Vehicle not found"}, status=404)
        
@csrf_exempt
def add_city_vehicle_price(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            city_id = data.get("city_id")
            vehicle_type_id = data.get("vehicle_type_id")
            price_per_km = data.get("price_per_km")

            if not all([city_id, vehicle_type_id, price_per_km]):
                return JsonResponse({"error": "Missing required fields"}, status=400)

            # Import your models
            from .models import City, VehicleType, CityVehiclePrice

            city = City.objects.get(id=city_id)
            vehicle = VehicleType.objects.get(id=vehicle_type_id)

            # Check if entry already exists
            obj, created = CityVehiclePrice.objects.update_or_create(
                city=city,
                vehicle_type=vehicle,
                defaults={"price_per_km": price_per_km}
            )

            return JsonResponse({"success": True, "created": created})

        except City.DoesNotExist:
            return JsonResponse({"error": "City not found"}, status=404)
        except VehicleType.DoesNotExist:
            return JsonResponse({"error": "Vehicle type not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


def rental_vehicles(request):
    vehicles = RentedVehicle.objects.all().order_by('-id')
    context = {
        'current_url_name': "rental_vehicles",
        'vehicles': vehicles,
        'vehicle_count': vehicles.count()
    }
    return render(request, 'rental_vehicles.html', context)


def vehicle_details(request, vehicle_id):
    vehicle_data = RentedVehicle.objects.get(id=vehicle_id)
    vehicle_images = RentedVehicleImage.objects.filter(vehicle_id=vehicle_id)
    context = {
        'current_url_name': "rental_vehicles",
        'vehicle_data': vehicle_data,
        'vehicle_images': vehicle_images,
        'vehicle_id': vehicle_id
    }
    return render(request, 'vehicle_details.html', context)

def add_promo_code(request):
    if request.method == 'POST':
        try:
            from decimal import Decimal
            from urllib.parse import quote

            ist = pytz.timezone('Asia/Kolkata')

            code = request.POST.get('code')
            description = request.POST.get('description', '')
            discount_type = request.POST.get('discount_type')
            discount_value = Decimal(request.POST.get('discount_value'))
            max_discount_amount = Decimal(request.POST.get('max_discount_amount')) if request.POST.get('max_discount_amount') else None
            min_ride_amount = Decimal(request.POST.get('min_ride_amount')) if request.POST.get('min_ride_amount') else 0
            usage_limit_per_user = int(request.POST.get('usage_limit_per_user'))
            total_usage_limit = int(request.POST.get('total_usage_limit')) if request.POST.get('total_usage_limit') else None

            # Parse and convert to UTC
            raw_valid_from = parse_datetime(request.POST.get('valid_from'))
            raw_valid_to = parse_datetime(request.POST.get('valid_to'))

            # Localize to IST and then convert to UTC
            valid_from = ist.localize(raw_valid_from).astimezone(pytz.UTC)
            valid_to = ist.localize(raw_valid_to).astimezone(pytz.UTC)

            is_active = request.POST.get('is_active') == 'on'

            PromoCode.objects.create(
                code=code,
                description=description,
                discount_type=discount_type,
                discount_value=discount_value,
                max_discount_amount=max_discount_amount,
                min_ride_amount=min_ride_amount,
                usage_limit_per_user=usage_limit_per_user,
                total_usage_limit=total_usage_limit,
                valid_from=valid_from,
                valid_to=valid_to,
                is_active=is_active,
            )

            return redirect('/add-promo-code/?created=1')
        except Exception as e:
            return redirect(f'/add-promo-code/?error={quote(str(e))}')

    return render(request, 'add_promo_code.html', {'current_url_name': "promo_code"})

def promo_code(request):
    promo_codes = PromoCode.objects.order_by('-id')
    context = {
        'current_url_name':'promo_code',
        'promo_codes':promo_codes
    }
    return render(request,'promo_code.html',context)


def delete_promo(request, pk):
    if request.method == "POST":
        try:
            promo = PromoCode.objects.get(pk=pk)
            promo.delete()
            return JsonResponse({"success": True})
        except PromoCode.DoesNotExist:
            return JsonResponse({"error": "Promo code not found"}, status=404)

# ride sharing code 
def ride_sharing_request(request):
    vehicles = RideShareVehicle.objects.select_related('owner').all().order_by('-created_at')

    context = {
        "current_url_name": "ride_sharing",
        "vehicles": vehicles
    }
    return render(request, 'ride_sharing_request.html', context)


def sharing_vehicle_details(request,id):
    vehicle_data = RideShareVehicle.objects.get(id=id)
    context = {
        'vehicle_data':vehicle_data,
        "current_url_name": "ride_sharing"
    }
    return render(request,'sharing_vehicle_details.html',context)

def verify_sharing_vehicle(request, vehicle_id):
    if request.method == "POST":
        try:
            vehicle_info = RideShareVehicle.objects.get(id=vehicle_id)
            vehicle_info.approved = True
            vehicle_info.save()
            return JsonResponse({"status": "success"})
        except DriverDocumentInfo.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Vehicle not found"}, status=404)
        
def disapprove_sharing_vehicle(request, vehicle_id):
    if request.method == "POST":
        try:
            vehicle_info = RideShareVehicle.objects.get(id=vehicle_id)
            vehicle_info.approved = False
            vehicle_info.save()
            return JsonResponse({"status": "success"})
        except DriverDocumentInfo.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Document not found"}, status=404)
        
def cash_out_requests(request):
    requests = CashOutRequest.objects.select_related('driver').order_by('-requested_at')

    context = {
        'current_url_name': "cash_out",
        'requests': requests
    }
    return render(request, 'cash_out_requests.html', context)

def user_profile(request, user_id):
    driver = get_object_or_404(CustomUser, id=user_id, role='driver')

    recent_rides = RideRequest.objects.filter(driver=driver).order_by('-created_at')[:5]
    latest_cashout = CashOutRequest.objects.filter(driver=driver).order_by('-requested_at').first()
    ride_data = []
    for ride in recent_rides:
        payment = getattr(ride, 'payment_detail', None)
        rating = getattr(ride, 'driver_rating', None)

        ride_data.append({
            'ride': ride,
            'payment': payment,
            'rating': rating,
            'promo_code': payment.promo_code if payment else None,
            'promo_discount': payment.promo_discount if payment else 0,
        })

    recent_transactions = DriverWalletTransaction.objects.filter(driver=driver).order_by('-created_at')[:5]

    avg_rating = DriverRating.objects.filter(driver=driver).aggregate(avg=Avg('rating'))['avg'] or 0

    context = {
        'driver': driver,
        'ride_data': ride_data,
        'recent_transactions': recent_transactions,
        'current_url_name': 'cash_out',
        'avg_rating': avg_rating,
        'latest_cashout': latest_cashout,
    }
    return render(request, 'user_profile.html', context)

def process_cash_out(request, cashOut_id):
    if request.method == "POST":
        try:
            obj = CashOutRequest.objects.get(id=cashOut_id)
            obj.status = "processed"
            obj.save()
            return JsonResponse({"status": "success"})
        except DriverDocumentInfo.DoesNotExist:
            return JsonResponse({"status": "error"}, status=404)
        






# Corporate side code
def corporate_requests(request):
    ist = pytz.timezone("Asia/Kolkata")  # ✅ Correct usage
    companies = CompanyAccount.objects.select_related("admin_user")
    for company in companies:
        company.applied_ist = localtime(company.created_at, ist).strftime("%b %d, %Y at %I:%M %p")
    context = {
        'companies': companies,
        'current_url_name':"corporate_request"
    }
    return render(request, 'corporate_requests.html', context)

def company_details(request, company_id):
    company = get_object_or_404(CompanyAccount, id=company_id)
    admin_user = company.admin_user  # related OneToOne user
    return render(request, 'company_details.html', {
        'company': company,
        'admin_user': admin_user,
        'current_url_name':"corporate_request"
    })

def approve_company(request, company_id):
    if request.method == "POST":
        try:
            obj = CompanyAccount.objects.get(id=company_id)
            obj.is_approved = True
            obj.save()
            return JsonResponse({"status": "success"})
        except CompanyAccount.DoesNotExist:
            return JsonResponse({"status": "error"}, status=404)


@login_required
def delete_company(request, company_id):
    company = get_object_or_404(CompanyAccount, id=company_id)
    
    # Optional: Check user permissions here if needed
    if request.method == 'POST':
        company_name = company.company_name
        company.delete()  # This will also delete the related admin user due to on_delete=models.CASCADE
        # messages.success(request, f"Company '{company_name}' and its corporate admin have been deleted.")
        return redirect('corporate_requests')  # Or any list view of companies
    
    # messages.error(request, "Invalid request.")
    return redirect('company_details', company_id=company_id)  

# add_prepaid_plan

def prepaid_plans(request):
    plans = PrepaidPlan.objects.all().order_by('-created_at')
    context = {
        "current_url_name": "prepaid",
        "prepaid_plans": plans
    }
    return render(request, 'prepaid_plans.html',context)

def add_prepaid_plan(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            price = request.POST.get('price')
            validity_type = request.POST.get('validity_type')
            validity_days = request.POST.get('validity_days')
            credits_provided = request.POST.get('credits_provided')
            description = request.POST.get('description')
            benefits = request.POST.get('benefits')
            is_active = request.POST.get('is_active') == 'on'

            PrepaidPlan.objects.create(
                name=name,
                price=price,
                validity_type=validity_type,
                validity_days=validity_days,
                credits_provided=credits_provided,
                description=description,
                benefits=benefits,
                is_active=is_active,
            )

            return redirect(f"{reverse('add_prepaid_plan')}?created=1")

        except Exception as e:
            error_message = str(e).replace(' ', '+')
            return redirect(f"{reverse('add_prepaid_plan')}?error={error_message}")

    return render(request, 'add_prepaid_plan.html')

@csrf_exempt
def delete_prepaid_plan(request, plan_id):
    if request.method == 'POST':
        try:
            plan = PrepaidPlan.objects.get(id=plan_id)
            plan.delete()
            return JsonResponse({'success': True})
        except PrepaidPlan.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Plan not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


def reports(request):
    report_submissions = RideReportSubmission.objects.select_related(
        'ride__user', 'ride__driver', 'report_type'
    ).order_by('-submitted_at')

    context = {
        'report_submissions': report_submissions,
        'current_url_name': 'reports'
    }
    return render(request, 'reports.html', context)


def delete_account_view(request):
    if request.method == "POST":
        phone = request.POST.get("phone_number")
        password = request.POST.get("password")

        # Authenticate using phone_number and password
        user = authenticate(request, phone_number=phone, password=password)

        if user is not None:
            # Delete the account
            user.delete()
            messages.success(request, f"Account with phone {phone} deleted successfully!")
            return HttpResponseRedirect(reverse("delete_account"))
        else:
            messages.error(request, "Invalid phone number or password!")

    return render(request, "delete_account.html")