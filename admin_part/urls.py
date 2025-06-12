from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',views.dashboard,name="dashboard"),
    path('login/', views.login_view, name='login'),
    path('approve_drivers/',views.approve_drivers,name="approve_drivers"),
    path('driver_details/<int:driver_id>/',views.driver_details,name="driver_details"),
    path('add-city/', views.add_city, name='add_city'),
    path('add-vehicle-type/', views.add_vehicle_type, name='add_vehicle_type'),
    path('verify-driver/<int:driver_id>/', views.verify_driver, name='verify_driver'),
    path('block-driver/<int:driver_id>/', views.block_driver, name='block_driver'),
    path('fare_management',views.fare_management,name="fare_management"),
    path('cab_management',views.cab_management,name="cab_management"),
    path('get-vehicle-type/<int:pk>/', views.get_vehicle_type, name='get_vehicle_type'),
    path('update-vehicle-type/<int:pk>/', views.update_vehicle_type, name='update_vehicle_type'),
    path("delete-city/<int:pk>/", views.delete_city, name="delete_city"),
    path("delete-vehicle/<int:pk>/", views.delete_vehicle, name="delete_vehicle"),
    path('add-city-vehicle-price/', views.add_city_vehicle_price, name='add_city_vehicle_price'),
    path("delete-vehicle-price/<int:pk>/", views.delete_vehicle_price, name="delete_vehicle_price"),
    path("rental_vehicles",views.rental_vehicles,name="rental_vehicles"),
    path('vehicle_details/<int:vehicle_id>/',views.vehicle_details,name="vehicle_details"),
    path('verify-rental-vehicle/<int:vehicle_id>/', views.verify_rental_vehicle, name='verify_rental_vehicle'),
    path('disapprove-rental-vehicle/<int:vehicle_id>/', views.disapprove_rental_vehicle, name='disapprove_rental_vehicle'),

    # 12-6-25
    path('add-promo-code/',views.add_promo_code,name="add_promo_code"),
]