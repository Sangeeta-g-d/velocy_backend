from rest_framework import serializers
from rider_part.models import *
from django.contrib.auth import get_user_model
from admin_part.models import City, VehicleType
from rider_part.models import RideRequest, RideStop
import pytz
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

    class Meta:
        model = RideRequest
        fields = '__all__'

    
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