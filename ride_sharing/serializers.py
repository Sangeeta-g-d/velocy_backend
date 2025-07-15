from rest_framework import serializers
from .models import RideShareVehicle,RideShareBooking
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
        exclude = ['user', 'status', 'created_at', 'distance_km', 'price']

    def validate(self, attrs):
        vehicle_id = self.initial_data.get('vehicle')
        passengers = attrs.get('passengers_count')

        if vehicle_id and passengers:
            try:
                vehicle_obj = RideShareVehicle.objects.get(id=vehicle_id)
                if passengers > vehicle_obj.seat_capacity:
                    raise serializers.ValidationError("Passenger count exceeds vehicle seat capacity.")
            except RideShareVehicle.DoesNotExist:
                raise serializers.ValidationError("Vehicle does not exist.")

        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user  # Always use token-authenticated user
        validated_data['status'] = 'draft'
        return RideShareBooking.objects.create(**validated_data)
