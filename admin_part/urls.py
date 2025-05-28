from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',views.dashboard,name="dashboard"),
    path('login/', views.login_view, name='login'),
    path('approve_drivers/',views.approve_drivers,name="approve_drivers"),
    path('driver_details/<int:driver_id>/',views.driver_details,name="driver_details"),
]