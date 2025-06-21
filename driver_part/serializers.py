from rest_framework import serializers
from rider_part.models import *
from django.contrib.auth import get_user_model
from admin_part.models import City, VehicleType
from rider_part.models import RideRequest, RideStop
import pytz
from auth_api.models import DriverDocumentInfo

from django.utils.timezone import localtime
User = get_user_model()


class CashLimitSerializer(serializers.Serializer):
    cash_payments_left = serializers.IntegerField()


class RideNowDestinationSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = ['id','to_location', 'to_latitude', 'to_longitude', 'price']

    def get_price(self, obj):
        return obj.offered_price if obj.offered_price is not None else obj.estimated_price
    

class RideStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideStop
        fields = ['id', 'location', 'latitude', 'longitude', 'order']

class RideRequestDetailSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    city = serializers.StringRelatedField()
    vehicle_type = serializers.StringRelatedField()
    ride_stops = RideStopSerializer(many=True, read_only=True)
    created_at = serializers.SerializerMethodField()
    class Meta:
        model = RideRequest
        fields = '__all__'
        
    def get_created_at(self, obj):
        # Convert to Indian time
        india_tz = pytz.timezone("Asia/Kolkata")
        local_dt = localtime(obj.created_at, india_tz)
        return local_dt.strftime('%d-%m-%Y %I:%M %p')

    
class DeclineRideSerializer(serializers.Serializer):
    ride_id = serializers.IntegerField()

    def validate_ride_id(self, value):
        from driver_part.models import RideRequest  # Adjust import path if needed
        if not RideRequest.objects.filter(id=value).exists():
            raise serializers.ValidationError("Ride with this ID does not exist.")
        return value


class RideStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideStop
        fields = ['location','order']


class RiderInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username','phone_number']  # Adjust to your User model


class RideAcceptedDetailSerializer(serializers.ModelSerializer):
    ride_stops = RideStopSerializer(many=True)
    rider = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    scheduled_time = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = [
            'id', 'from_location', 'to_location',
            'ride_type', 'status', 'created_at',
            'scheduled_time', 'ride_stops', 'rider'
        ]

    def get_rider(self, obj):
        return RiderInfoSerializer(obj.user).data

    def format_datetime_to_ist(self, dt):
        if dt is None:
            return None
        ist = pytz.timezone("Asia/Kolkata")
        dt_ist = localtime(dt, timezone=ist)
        return dt_ist.strftime("%d-%m-%Y %I:%M %p")  # Example: 04-06-2025 03:45 PM

    def get_created_at(self, obj):
        return self.format_datetime_to_ist(obj.created_at)

    def get_scheduled_time(self, obj):
        return self.format_datetime_to_ist(obj.scheduled_time)
    

class RiderInformationSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['username', 'profile', 'phone_number']

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.profile and hasattr(obj.profile, 'url'):
            return request.build_absolute_uri(obj.profile.url) if request else obj.profile.url
        return None

class RideDetailSerializer(serializers.ModelSerializer):
    ride_stops = RideStopSerializer(many=True, read_only=True)
    user = RiderInformationSerializer()

    class Meta:
        model = RideRequest
        fields = [
            'from_location', 'to_location',
            'ride_stops',  # Related name in RideStop model
            'user'  # Rider info
        ]

class RidePriceDetailSerializer(serializers.ModelSerializer):
    ride_stops = RideStopSerializer(many=True, read_only=True)

    class Meta:
        model = RideRequest
        fields = [
            'id',
            'from_location', 'from_latitude', 'from_longitude',
            'to_location', 'to_latitude', 'to_longitude',
            'distance_km', 'offered_price',
            'ride_stops',
        ]


class DriverProfileSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['username', 'profile']

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.profile and hasattr(obj.profile, 'url'):
            return request.build_absolute_uri(obj.profile.url) if request else obj.profile.url
        return None
    

class DriverRideHistorySerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    amount_received = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = [
            'id', 'from_location', 'to_location',
            'date', 'start_time', 'amount_received', 'payment_method'
        ]

    def get_date(self, obj):
        if obj.start_time:
            ist = pytz.timezone("Asia/Kolkata")
            ist_time = obj.start_time.astimezone(ist)
            today = timezone.now().astimezone(ist).date()
            ride_date = ist_time.date()

            if ride_date == today:
                return "Today"
            elif ride_date == (today - timedelta(days=1)):
                return "Yesterday"
            return ist_time.strftime('%Y-%m-%d')
        return None

    def get_start_time(self, obj):
        if obj.start_time:
            ist_time = obj.start_time.astimezone(pytz.timezone("Asia/Kolkata"))
            return ist_time.strftime('%I:%M %p')
        return None

    def get_amount_received(self, obj):
        payment = getattr(obj, 'payment_detail', None)
        return float(payment.grand_total) if payment else 0.0

    def get_payment_method(self, obj):
        payment = getattr(obj, 'payment_detail', None)
        return payment.payment_method if payment else None


# vehicle docs
class DriverDocumentSerializer(serializers.ModelSerializer):
    vehicle_registration_doc = serializers.SerializerMethodField()
    driver_license = serializers.SerializerMethodField()
    vehicle_insurance = serializers.SerializerMethodField()

    class Meta:
        model = DriverDocumentInfo
        fields = [
            'id',
            'license_plate_number',
            'vehicle_registration_doc',
            'driver_license',
            'vehicle_insurance',
            'verified',
        ]

    def get_vehicle_registration_doc(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.vehicle_registration_doc.url) if obj.vehicle_registration_doc else None

    def get_driver_license(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.driver_license.url) if obj.driver_license else None

    def get_vehicle_insurance(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.vehicle_insurance.url) if obj.vehicle_insurance else None