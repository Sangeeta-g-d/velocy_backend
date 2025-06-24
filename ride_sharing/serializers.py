from rest_framework import serializers
from .models import RideShareVehicle,Ride,RideJoinRequest
from ride_sharing.time_utils import convert_to_ist


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
        ist_time = convert_to_ist(obj.created_at)
        return ist_time.strftime("%Y-%m-%d %H:%M:%S")
    
class RideCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = [
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'available_seats',
            'notes',
        ]

class RideSerializer(serializers.ModelSerializer):
    ride_date = serializers.DateField(format="%Y-%m-%d")
    ride_time = serializers.TimeField(format="%H:%M")
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Ride
        fields = [
            'id',
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'available_seats',
            'notes',
            'created_at',
        ]

    def get_created_at(self, obj):
        return convert_to_ist(obj.created_at).strftime("%Y-%m-%d %H:%M:%S")


class PublicRideSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='driver.username', read_only=True)
    creator_profile = serializers.ImageField(source='driver.profile', read_only=True)
    creator_phone_number = serializers.CharField(source='driver.phone_number', read_only=True)
    ride_date = serializers.DateField(format="%Y-%m-%d")
    ride_time = serializers.TimeField(format="%H:%M")
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Ride
        fields = [
            'id',
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'available_seats',
            'notes',
            'creator_username',
            'creator_profile',
            'creator_phone_number',
            'created_at',
        ]

    def get_created_at(self, obj):
        return convert_to_ist(obj.created_at).strftime("%Y-%m-%d %H:%M:%S")
    
class RideJoinRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideJoinRequest
        fields = ['seats_requested']

    def validate(self, attrs):
        request = self.context['request']
        ride = self.context['ride']

        if ride.driver == request.user:
            raise serializers.ValidationError("You cannot request to join your own ride.")

        if RideJoinRequest.objects.filter(user=request.user, ride=ride).exclude(status='cancelled').exists():
            raise serializers.ValidationError("You have already requested to join this ride.")

        if attrs['seats_requested'] > ride.available_seats:
            raise serializers.ValidationError("Requested seats exceed available seats.")

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        ride = self.context['ride']
        return RideJoinRequest.objects.create(
            user=user,
            ride=ride,
            **validated_data
        )