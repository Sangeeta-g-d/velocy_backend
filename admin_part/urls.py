from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',views.dashboard,name="dashboard"),
    path('login/', views.login_view, name='login'),
    path('logout/',views.logout_view,name="logout"),
    path('approve_drivers/',views.approve_drivers,name="approve_drivers"),
    path('driver_details/<int:driver_id>/',views.driver_details,name="driver_details"),
    path('get_indian_cities/', views.get_indian_cities, name='get_indian_cities'),
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
    path('users_list/',views.users_list,name="users_list"),

    # 12-6-25
    path('add-promo-code/',views.add_promo_code,name="add_promo_code"),

    # 17-6-25
    path('promo_code/',views.promo_code,name="promo_code"),
    path('delete_promo/<int:pk>/',views.delete_promo,name="delete_promo"),


    # 23-6-25 ride sharing
    path('ride_sharing_request/',views.ride_sharing_request,name="ride_sharing_request"),
    path('sharing_vehicle_details/<int:id>/',views.sharing_vehicle_details,name="sharing_vehicle_details"),
    path('disapprove_sharing_vehicle/<int:vehicle_id>/',views.disapprove_sharing_vehicle,name="disapprove_sharing_vehicle"),
    path('verify_sharing_vehicle/<int:vehicle_id>/',views.verify_sharing_vehicle,name="verify_sharing_vehicle"),

    # 25-6-25
    path('cash_out_requests/',views.cash_out_requests,name="cash_out_requests"),
    path('user_profile/<int:user_id>/',views.user_profile,name="user_profile"),
    path('process-cash-out/<int:cashOut_id>/', views.ProcessCashOutView.as_view(), name="process_cash_out"),
    # driver role
    path('change_driver_role/<int:driver_id>/', views.change_driver_role, name='update_driver_role'),
    path('reports/', views.reports, name='reported_drivers'),
    path("edit-promo-codes/<int:promo_id>/", views.edit_promo_code, name="edit_promo_code"),
    path("delete-driver/<int:driver_id>/", views.delete_driver, name="delete_driver"),
    path("delete-user/<int:user_id>/", views.delete_user, name="delete_user"),





    # corporate urls
    path('corporate_requests/',views.corporate_requests,name="corporate_requests"),
    path('company_details/<int:company_id>/',views.company_details,name="company_details"),
    path('companies/<int:company_id>/delete/', views.delete_company, name='delete_company'),
    path('approve-company/<int:company_id>/',views.approve_company,name="approve_company"),
    path('add_prepaid_plan/',views.add_prepaid_plan,name="add_prepaid_plan"),
    path('prepaid_plans/',views.prepaid_plans,name="prepaid_plans"),
    path('delete_prepaid_plan/<int:plan_id>/', views.delete_prepaid_plan, name='delete_prepaid_plan'),
    path("edit_prepaid_plan/<int:plan_id>/", views.edit_prepaid_plan, name="edit_prepaid_plan"),


    path('delete-account/',views.delete_account_view,name="delete_account"),


    path('settings/', views.settings_view, name='settings'),
    # Platform settings
    path('settings/platform/add/', views.add_platform_setting, name='add_platform_setting'),
    path('settings/platform/update/<int:setting_id>/', views.update_platform_setting, name='update_platform_setting'),
    path('settings/platform/delete/<int:setting_id>/', views.delete_platform_setting, name='delete_platform_setting'),

    # Ride reports
    path('settings/report/add/', views.add_ride_report, name='add_ride_report'),
    path('settings/report/update/<int:report_id>/', views.update_ride_report, name='update_ride_report'),
    path('settings/report/delete/<int:report_id>/', views.delete_ride_report, name='delete_ride_report'),



    # share ride
    path("share-ride/<int:ride_id>/", views.share_ride_view, name="share_ride"),
    path("link_expiryd/", views.link_expiryd, name="link_expiryd"),
    path("session_not_found/", views.session_not_found, name="session_not_found"),
    path("ride-route/<int:ride_id>/", views.ride_route_view, name="ride_route"),
    path("ride-not-available/", views.ride_not_available, name="ride_not_available"),

]
    
