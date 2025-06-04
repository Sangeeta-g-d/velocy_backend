from rest_framework import serializers
from rider_part.models import *
from django.contrib.auth import get_user_model
from admin_part.models import City, VehicleType
from rider_part.models import RideRequest, RideStop

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