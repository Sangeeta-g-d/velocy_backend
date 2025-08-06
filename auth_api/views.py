# views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import *
from .models import PhoneOTP, CustomUser
from rest_framework.permissions import AllowAny
from twilio.base.exceptions import TwilioRestException
from .utils.otp import generate_otp, send_otp
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ObjectDoesNotExist
import traceback

class SendOTPView(APIView):
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone_number']
            mode = request.query_params.get('mode')  # 'login' or 'register'

            if mode == 'login' and not CustomUser.objects.filter(phone_number=phone).exists():
                return Response({'error': 'User does not exist. Please register.'}, status=status.HTTP_404_NOT_FOUND)

            if mode == 'register' and CustomUser.objects.filter(phone_number=phone).exists():
                return Response({'error': 'User already exists. Please login.'}, status=status.HTTP_400_BAD_REQUEST)

            otp = generate_otp()
            print(f"Phone received: {phone}")
            print(f"Mode: {mode}")
            print(f"Generated OTP: {otp}")
            print("Attempting to send OTP...")

            try:
                send_otp(phone, otp)
            except TwilioRestException as e:
                print("Twilio Error:")
                print(str(e))
                traceback.print_exc()  # Full error trace
                return Response({
                    'message': 'OTP could not be sent via SMS.',
                    'twilio_error': str(e)  # This will return the actual Twilio error
                }, status=status.HTTP_400_BAD_REQUEST)

            # Save OTP if sending succeeded
            PhoneOTP.objects.update_or_create(
                phone_number=phone,
                defaults={'otp': otp, 'created_at': timezone.now()}
            )
            return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterWithOTPView(APIView):
    MASTER_OTP = '112233'  # define master OTP

    def post(self, request):
        serializer = RegisterWithOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone_number']
            otp = serializer.validated_data['otp']
            password = serializer.validated_data['password']

            try:
                phone_otp = PhoneOTP.objects.get(phone_number=phone)

                if otp != self.MASTER_OTP:
                    if phone_otp.otp != otp:
                        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
                    if phone_otp.is_expired():
                        return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

                # Register or get the user
                user, created = CustomUser.objects.get_or_create(phone_number=phone)

                # Set password
                user.password = make_password(password)

                # Default role (if just created)
                if created:
                    user.role = 'rider'
                user.save()

                # Clean up OTP (optional)
                if otp != self.MASTER_OTP:
                    phone_otp.delete()

                return Response({
                    'message': 'User registered successfully',
                    'user_id': user.id
                }, status=status.HTTP_201_CREATED)

            except PhoneOTP.DoesNotExist:
                if otp == self.MASTER_OTP:
                    # Proceed even if OTP record is missing
                    user, created = CustomUser.objects.get_or_create(phone_number=phone)
                    user.password = make_password(password)
                    if created:
                        user.role = 'rider'
                    user.save()

                    return Response({
                        'message': 'User registered successfully with master OTP',
                        'user_id': user.id
                    }, status=status.HTTP_201_CREATED)

                return Response({'error': 'Please request an OTP first'}, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginWithOTPView(APIView):
    MASTER_OTP = '112233'  # your master OTP

    def post(self, request):
        serializer = LoginOTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone_number']
            otp = serializer.validated_data['otp']

            # Check if user exists
            try:
                user = CustomUser.objects.get(phone_number=phone)
            except CustomUser.DoesNotExist:
                return Response({'error': 'User does not exist. Please register.'}, status=status.HTTP_404_NOT_FOUND)

            # Check OTP
            try:
                phone_otp = PhoneOTP.objects.get(phone_number=phone)

                if otp != self.MASTER_OTP:
                    if phone_otp.otp != otp:
                        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
                    if phone_otp.is_expired():
                        return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

                # Delete OTP after successful check (unless master used)
                if otp != self.MASTER_OTP:
                    phone_otp.delete()

            except PhoneOTP.DoesNotExist:
                if otp != self.MASTER_OTP:
                    return Response({'error': 'Please request an OTP first'}, status=status.HTTP_404_NOT_FOUND)

            # 🚫 Driver Role Check Before Login
            if user.role == 'driver':
                doc = getattr(user, 'document_info', None)
                if not doc or not doc.verified:
                    return Response({'error': 'Approval pending. Please wait for admin verification.'}, status=status.HTTP_403_FORBIDDEN)

            # 🚫 Employee Role Check
            if user.role == 'employee':
                credit = getattr(user, 'credit', None)
                if not credit or not credit.is_active:
                    return Response({'error': 'Your account is not active. Please contact your company admin.'},
                                    status=status.HTTP_403_FORBIDDEN)

            # ✅ Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user': {
                    'phone_number': user.phone_number,
                    'role': user.role,
                    'user_id': user.id
                },
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# login with phone and password
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # ✅ Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful",
            "user": {
                "user_id": user.id,
                "phone_number": user.phone_number,
                "role": user.role,
            },
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)

# update profile 
class UpdateUserProfileView(APIView):
    def put(self, request):
        user_id = request.data.get('user_id')

        if not user_id:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except ObjectDoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserProfileUpdateSerializer(instance=user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class BecomeDriverView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')

        if not user_id:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except ObjectDoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        user.role = 'driver'
        user.save()

        return Response({
            'message': 'Role updated to driver successfully.',
            'role': user.role
        }, status=status.HTTP_200_OK)
    

# vehicle information code
class DriverVehicleInfoView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except ObjectDoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Remove user_id from validated data to avoid serializer errors
        data = request.data.copy()
        data.pop('user_id', None)

        serializer = DriverVehicleInfoSerializer(data=data)
        if serializer.is_valid():
            vehicle_info, created = DriverVehicleInfo.objects.update_or_create(
                user=user,
                defaults=serializer.validated_data
            )
            return Response({
                'message': 'Vehicle info saved successfully',
                'data': DriverVehicleInfoSerializer(vehicle_info).data
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class DriverDocumentInfoView(APIView):
    parser_classes = [MultiPartParser, FormParser]  # needed for file uploads

    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except ObjectDoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data.pop('user_id', None)

        serializer = DriverDocumentInfoSerializer(data=data)
        if serializer.is_valid():
            doc_info, created = DriverDocumentInfo.objects.update_or_create(
                user=user,
                defaults=serializer.validated_data
            )
            return Response({
                'message': 'Driver document information saved successfully',
                'data': DriverDocumentInfoSerializer(doc_info).data
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

