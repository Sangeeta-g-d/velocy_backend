from rest_framework import serializers
from .models import *


class EstimatedPriceInputSerializer(serializers.Serializer):
    city_name = serializers.CharField(max_length=100)
    start_location_name = serializers.CharField(max_length=255)
    end_location_name = serializers.CharField(max_length=255)
    distance_km = serializers.DecimalField(max_digits=6, decimal_places=2)

class CarPoolRideSerializer(serializers.ModelSerializer):
    start_location_name = serializers.CharField(required=True)
    start_latitude = serializers.FloatField(required=True)
    start_longitude = serializers.FloatField(required=True)

    end_location_name = serializers.CharField(required=True)
    end_latitude = serializers.FloatField(required=True)
    end_longitude = serializers.FloatField(required=True)

    date = serializers.DateField(required=True)
    time = serializers.TimeField(required=True)

    total_seats = serializers.IntegerField(required=True, min_value=1)
    final_price = serializers.DecimalField(required=True, max_digits=10, decimal_places=2)

    estimated_duration = serializers.DurationField(required=True)
    distance_km = serializers.DecimalField(required=True, max_digits=6, decimal_places=2)
    driver_notes = serializers.CharField(required=True)

    class Meta:
        model = CarPoolRide
        fields = '__all__'
        read_only_fields = ['available_seats', 'driver', 'created_at']

    def create(self, validated_data):
        validated_data['available_seats'] = validated_data['total_seats']
        return super().create(validated_data)
    
class RideStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideStop
        fields = ['id', 'ride', 'location_name', 'latitude', 'longitude']
        read_only_fields = ['id', 'ride']