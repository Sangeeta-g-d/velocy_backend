# serializers.py

from rest_framework import serializers
from .models import CustomUser, PhoneOTP,DriverVehicleInfo,DriverDocumentInfo
import re

class SendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        pattern = r'^\+91[6-9]\d{9}$'  # Matches +91 followed by 10 digits starting with 6-9
        if not re.match(pattern, value):
            raise serializers.ValidationError("Phone number must be in the format +91XXXXXXXXXX with 10 digits.")
        return value

class LoginOTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp = serializers.CharField()

class RegisterWithOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'profile',
            'username',
            'gender',
            'street',
            'area',
            'aadhar_card',
            'address_type',
        ]

class DriverVehicleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverVehicleInfo
        fields = ['vehicle_number', 'vehicle_type', 'year', 'car_company', 'car_model']

class DriverDocumentInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverDocumentInfo
        fields = [
            'license_plate_number',
            'vehicle_registration_doc',
            'driver_license',
            'vehicle_insurance'
        ]