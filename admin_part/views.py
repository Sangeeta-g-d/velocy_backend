from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from auth_api.models import CustomUser
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
    drivers = CustomUser.objects.filter(role='driver')
    context = {
        "current_url_name":"approve_drivers",
        'drivers': drivers
    }
    return render(request, 'approve_drivers.html', context)

def driver_details(request, driver_id):
    driver = get_object_or_404(CustomUser, id=driver_id)
    vehicle_info = getattr(driver, 'vehicle_info', None)
    document_info = getattr(driver, 'document_info', None)

    documents = []

    if document_info:
        if document_info.vehicle_registration_doc:
            documents.append({
                "name": "Registration Certificate (RC)",
                "url": document_info.vehicle_registration_doc.url
            })
        if document_info.vehicle_insurance:
            documents.append({
                "name": "Insurance",
                "url": document_info.vehicle_insurance.url
            })
        if document_info.driver_license:
            documents.append({
                "name": "Driver License",
                "url": document_info.driver_license.url
            })
    if driver.aadhar_card:
        documents.append({
            "name": "Aadhar Document",
            "url": driver.aadhar_card.url
        })

    context = {
        "driver": driver,
        "vehicle_info": vehicle_info,
        "documents": documents,
    }
    return render(request, 'driver_details.html', context)