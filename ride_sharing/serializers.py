from rest_framework import serializers
from .models import RideShareVehicle,RideShareBooking,RideShareStop
from ride_sharing.time_utils import convert_to_ist
from pytz import timezone as pytz_timezone
# from notifications.utils import send_fcm_notification
from datetime import datetime

class RideShareVehicleSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = RideShareVehicle
        fields = [
            'id',
            'vehicle_number',
            'model_name',
            'seat_capacity',
            'registration_doc',
            'aadhar_card',
            'driving_license',
            'approved',
            'created_at',
        ]

    def get_created_at(self, obj):
        return convert_to_ist(obj.created_at)

    def validate_vehicle_number(self, value):
        value = value.upper()
        if RideShareVehicle.objects.filter(vehicle_number__iexact=value).exists():
            raise serializers.ValidationError("This vehicle number is already registered.")
        return value

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class RideShareBookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideShareBooking
        exclude = ['user', 'status', 'created_at', 'price']  # keep price optional, distance required

    def validate(self, attrs):
        vehicle_id = self.initial_data.get('vehicle')
        passengers = attrs.get('passengers_count')
        distance = attrs.get('distance_km')

        if vehicle_id and passengers:
            try:
                vehicle_obj = RideShareVehicle.objects.get(id=vehicle_id)
                if passengers > vehicle_obj.seat_capacity:
                    raise serializers.ValidationError("Passenger count exceeds vehicle seat capacity.")
            except RideShareVehicle.DoesNotExist:
                raise serializers.ValidationError("Vehicle does not exist.")

        if not distance or distance <= 0:
            raise serializers.ValidationError("Distance must be a positive number.")

        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['status'] = 'draft'
        return RideShareBooking.objects.create(**validated_data)


# add stops
class RideShareStopCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideShareStop
        fields = ['stop_location', 'stop_lat', 'stop_lng']

    def validate(self, attrs):
        lat = attrs.get('stop_lat')
        lng = attrs.get('stop_lng')

        if lat is None or lng is None:
            raise serializers.ValidationError("Latitude and longitude are required.")

        if not (-90 <= lat <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        if not (-180 <= lng <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")

        return attrs
