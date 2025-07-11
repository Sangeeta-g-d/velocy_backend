from django.urls import path
from .views import *
from . import views

urlpatterns = [
    path('register/',views.register,name="register"),
    path('company_dashboard/',views.company_dashboard,name="company_dashboard"),
    path('add_employee/',views.add_employee,name="add_employee"),
    path('employee_list/',views.employee_list,name="employee_list"),
    path('edit_employees/<int:employee_id>/', views.edit_employee_view, name='edit_employee'),
    path('employee_details/<int:employee_id>/',views.employee_details,name="employee_details"),
    path('choose_plan/',views.plans,name="plans"),
    path('create_order/<int:plan_id>/', views.create_razorpay_order, name='create_order'),
    path('payment_success/', views.payment_success, name='payment_success'),
    path('success_page/',views.success_page,name="success_page"),
    path('employee_activity/<int:employee_id>/', views.employee_activity, name='employee_activity'),

    # Corporate ride booking url
    path('book_ride/', views.book_ride, name='book_ride'),
]