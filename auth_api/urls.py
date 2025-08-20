from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterWithOTPView.as_view(), name='register-with-otp'),
    path('otp-login/', LoginWithOTPView.as_view(), name='login-with-otp'),
    path('profile-setup/', UpdateUserProfileView.as_view(), name='update-profile'),
    path('become-driver/', BecomeDriverView.as_view(), name='become-driver'),
    path('driver-registration/', DriverVehicleInfoView.as_view(), name='driver-vehicle-info'),
    path('document-upload/', DriverDocumentInfoView.as_view(), name='driver-document-info'),
    path("password-login/", LoginAPIView.as_view(), name="login"),
    path("firebase-auth/",FirebaseAuthView.as_view())

]
