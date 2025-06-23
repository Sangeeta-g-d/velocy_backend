from rest_framework import serializers
from .models import RideShareVehicle

class RideShareVehicleSerializer(serializers.ModelSerializer):
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
        ]

    def validate_vehicle_number(self, value):
        if RideShareVehicle.objects.filter(vehicle_number__iexact=value).exists():
            raise serializers.ValidationError("This vehicle number is already registered.")
        return value

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)