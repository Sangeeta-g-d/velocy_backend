from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from auth_api.models import CustomUser,DriverDocumentInfo
from .models import *
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from rent_vehicle.models import RentedVehicle,RentedVehicleImage
from django.utils.dateparse import parse_datetime
from urllib.parse import quote
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
            login(request, user)
            return redirect('dashboard')  # or your target view
        else:
            error = 'Invalid phone number or password.'

    return render(request, 'login.html', {'error': error})

def approve_drivers(request):
    drivers = CustomUser.objects.all()
    context = {
        "current_url_name":"approve_drivers",
        'drivers': drivers
    }
    return render(request, 'approve_drivers.html', context)

def driver_details(request, driver_id):
    driver = get_object_or_404(CustomUser, id=driver_id, role='driver')
    vehicle_info = getattr(driver, 'vehicle_info', None)
    document_info = getattr(driver, 'document_info', None)

    return render(request, 'driver_details.html', {
        'driver': driver,
        'vehicle_info': vehicle_info,
        'document_info': document_info,
        'current_url_name':'approve_drivers'
    })

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
        
def ride_sharing_request(request):
    context = {
        "current_url_name":"ride_sharing"
    }
    return render(request,'ride_sharing_request.html',context)