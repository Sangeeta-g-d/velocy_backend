# views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import *
from .models import PhoneOTP, CustomUser
from twilio.base.exceptions import TwilioRestException
from .utils.otp import generate_otp, send_otp
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

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

            try:
                send_otp(phone, otp)
            except TwilioRestException as e:
                # Handle the case where Twilio fails (e.g., trial number)
                return Response({
                    'message': 'OTP could not be sent via SMS. Use the Master OTP',
                    
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
                    user.role = 'rider'  # Set default role
                user.save()

                # Clean up OTP (optional if master was used)
                if otp != self.MASTER_OTP:
                    phone_otp.delete()

                # Generate tokens
                refresh = RefreshToken.for_user(user)

                return Response({
                    'message': 'User registered and logged in successfully',
                    'user': {
                        'phone_number': user.phone_number,
                        'role': user.role,
                    },
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_201_CREATED)

            except PhoneOTP.DoesNotExist:
                if otp == self.MASTER_OTP:
                    # Allow proceeding even if OTP record is missing, for master OTP
                    user, created = CustomUser.objects.get_or_create(phone_number=phone)
                    user.password = make_password(password)
                    if created:
                        user.role = 'rider'
                    user.save()

                    refresh = RefreshToken.for_user(user)
                    return Response({
                        'message': 'User registered with master OTP and logged in successfully',
                        'user': {
                            'phone_number': user.phone_number,
                            'role': user.role,
                        },
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
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

            # Check user exists
            try:
                user = CustomUser.objects.get(phone_number=phone)
            except CustomUser.DoesNotExist:
                return Response({'error': 'User does not exist. Please register.'}, status=status.HTTP_404_NOT_FOUND)

            # Check OTP record
            try:
                phone_otp = PhoneOTP.objects.get(phone_number=phone)

                if otp != self.MASTER_OTP:
                    if phone_otp.otp != otp:
                        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
                    if phone_otp.is_expired():
                        return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)

                # Optionally delete OTP record after use (for security)
                if otp != self.MASTER_OTP:
                    phone_otp.delete()

            except PhoneOTP.DoesNotExist:
                # If no OTP record but master OTP used, allow login
                if otp != self.MASTER_OTP:
                    return Response({'error': 'Please request an OTP first'}, status=status.HTTP_404_NOT_FOUND)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user': {
                    'phone_number': user.phone_number,
                    'role': user.role,
                },
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# update profile 
class UpdateUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = UserProfileUpdateSerializer(instance=request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully', 'user': serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class BecomeDriverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user.role = 'driver'
        user.save()
        return Response({
            'message': 'Role updated to driver successfully.',
            'role': user.role
        }, status=status.HTTP_200_OK)
    
# vehicle information code
class DriverVehicleInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DriverVehicleInfoSerializer(data=request.data)
        if serializer.is_valid():
            # Create or update the vehicle info
            vehicle_info, created = DriverVehicleInfo.objects.update_or_create(
                user=request.user,
                defaults=serializer.validated_data
            )
            return Response({
                'message': 'Vehicle info saved successfully',
                'data': DriverVehicleInfoSerializer(vehicle_info).data
            }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class DriverDocumentInfoView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Important for file uploads

    def post(self, request):
        serializer = DriverDocumentInfoSerializer(data=request.data)
        if serializer.is_valid():
            doc_info, created = DriverDocumentInfo.objects.update_or_create(
                user=request.user,
                defaults=serializer.validated_data
            )
            return Response({
                'message': 'Driver document information saved successfully',
                'data': DriverDocumentInfoSerializer(doc_info).data
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)