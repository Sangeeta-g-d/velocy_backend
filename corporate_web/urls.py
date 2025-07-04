from django.urls import path
from .views import *
from . import views

urlpatterns = [
    path('register/',views.register,name="register"),
    path('company_dashboard/',views.company_dashboard,name="company_dashboard"),
    path('add_employee/',views.add_employee,name="add_employee"),
    path('employee_list/',views.employee_list,name="employee_list"),
    path('employee_details/<int:employee_id>/',views.employee_details,name="employee_details")
]