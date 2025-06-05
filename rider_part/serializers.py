from rest_framework import serializers
from admin_part.models import VehicleType
from . models import *
from admin_part.models import City
from django.utils.timezone import localtime
import pytz


class VehicleTypeSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'number_of_passengers', 'image']

class RideRequestCreateSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(write_only=True)
    ride_type = serializers.ChoiceField(choices=RideRequest.RIDE_TYPE_CHOICES)

    class Meta:
        model = RideRequest
        fields = [
            'id',
            'ride_type',
            'city_name',
            'from_location', 'from_latitude', 'from_longitude',
            'to_location', 'to_latitude', 'to_longitude',
            'distance_km',
        ]

    def validate_city_name(self, value):
        cleaned = value.strip().lower()
        try:
            return City.objects.get(name__iexact=cleaned)
        except City.DoesNotExist:
            raise serializers.ValidationError(f"City '{cleaned}' not found.")

    def create(self, validated_data):
        city = validated_data.pop('city_name')
        user = self.context['request'].user
        return RideRequest.objects.create(
            user=user,
            city=city,
            status='draft',
            **validated_data
        )
    def validate(self, attrs):
        ride_type = attrs.get('ride_type')
        scheduled_time = attrs.get('scheduled_time')

        if ride_type == 'scheduled' and not scheduled_time:
            raise serializers.ValidationError({
                'scheduled_time': 'This field is required when ride_type is scheduled.'
            })

        return attrs
    

class RideStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideStop
        fields = ['id', 'ride', 'location', 'latitude', 'longitude', 'order']
        read_only_fields = ['order']  # Make order read-only so it's auto-generated 

class EstimatePriceInputSerializer(serializers.Serializer):
    ride_id = serializers.IntegerField()
    vehicle_type_id = serializers.IntegerField()


class RideRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = ['offered_price', 'women_only', 'status']