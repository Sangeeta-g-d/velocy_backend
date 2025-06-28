from rest_framework import serializers
from .models import RideShareVehicle,Ride,RideJoinRequest
from ride_sharing.time_utils import convert_to_ist
from pytz import timezone as pytz_timezone
# from notifications.utils import send_fcm_notification
from datetime import datetime

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
    available_seats = serializers.IntegerField(min_value=1, write_only=True)

    class Meta:
        model = Ride
        fields = [
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'available_seats',
            'price_per_person',   # 💰 Added here
            'notes',
        ]

    def create(self, validated_data):
        vehicle = self.context['vehicle']
        driver = self.context['driver']
        available_seats = validated_data.pop('available_seats')

        ride = Ride.objects.create(
            vehicle=vehicle,
            driver=driver,
            total_seats=available_seats,
            seats_left=available_seats,
            **validated_data
        )
        return ride
    
class RideSerializer(serializers.ModelSerializer):
    ride_date = serializers.DateField(format="%Y-%m-%d")
    ride_time = serializers.TimeField(format="%H:%M")
    created_at = serializers.SerializerMethodField()
    is_upcoming = serializers.SerializerMethodField()
    price_per_person = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)  # 💰 Added

    class Meta:
        model = Ride
        fields = [
            'id',
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'seats_left',
            'total_seats',
            'price_per_person', 
            'notes',
            'created_at',
            'is_upcoming',
        ]

    def get_created_at(self, obj):
        return convert_to_ist(obj.created_at)

    def get_is_upcoming(self, obj):
        ist = pytz_timezone('Asia/Kolkata')
        current_time = self.context.get('current_time', datetime.now(ist))
        ride_dt = ist.localize(datetime.combine(obj.ride_date, obj.ride_time))
        return ride_dt > current_time


class PublicRideSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='driver.username', read_only=True)
    creator_profile = serializers.ImageField(source='driver.profile', read_only=True)
    creator_phone_number = serializers.CharField(source='driver.phone_number', read_only=True)
    ride_date = serializers.DateField(format="%Y-%m-%d")
    ride_time = serializers.TimeField(format="%H:%M")
    created_at = serializers.SerializerMethodField()
    price_per_person = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)  # ✅ added

    class Meta:
        model = Ride
        fields = [
            'id',
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'seats_left',
            'price_per_person',  # ✅ include in output
            'notes',
            'creator_username',
            'creator_profile',
            'creator_phone_number',
            'created_at',
        ]

    def get_created_at(self, obj):
        return convert_to_ist(obj.created_at)

    
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

        if attrs['seats_requested'] > ride.seats_left:
            raise serializers.ValidationError("Requested seats exceed available seats.")

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        ride = self.context['ride']
        join_request = RideJoinRequest.objects.create(
            user=user,
            ride=ride,
            **validated_data
        )

        # ✅ Notify the ride driver
        # send_fcm_notification(
        #     user=ride.driver,
        #     title="New Ride Join Request",
        #     body=f"{user.name or user.username} has requested to join your ride from {ride.from_location} to {ride.to_location}.",
        #     data={
        #         "type": "join_request",
        #         "ride_id": ride.id,
        #         "join_request_id": join_request.id,
        #         "seats_requested": validated_data['seats_requested']
        #     }
        # )

        return join_request
    
class RideJoinRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    profile = serializers.SerializerMethodField()
    requested_at = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'id',
            'username',
            'profile',
            'seats_requested',
            'requested_at',
            'status'
        ]

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.user.profile and request:
            return request.build_absolute_uri(obj.user.profile.url)
        return None

    def get_requested_at(self, obj):
        from .time_utils import convert_to_ist  # ensure you're using the updated one
        return convert_to_ist(obj.requested_at)
    
class UserRequestedRideSerializer(serializers.ModelSerializer):
    from_location = serializers.CharField(source='ride.from_location')
    to_location = serializers.CharField(source='ride.to_location')
    ride_date = serializers.DateField(source='ride.ride_date')
    ride_time = serializers.TimeField(source='ride.ride_time')
    total_seats = serializers.IntegerField(source='ride.total_seats')
    available_seats = serializers.IntegerField(source='ride.seats_left')
    price_per_person = serializers.DecimalField(source='ride.price_per_person', max_digits=8, decimal_places=2)
    total_amount = serializers.SerializerMethodField()
    notes = serializers.CharField(source='ride.notes', allow_blank=True)
    vehicle_model = serializers.CharField(source='ride.vehicle.model_name')
    driver_username = serializers.CharField(source='ride.driver.username')
    driver_profile = serializers.SerializerMethodField()
    requested_at = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'id',
            'status',
            'seats_requested',
            'requested_at',
            'from_location',
            'to_location',
            'ride_date',
            'ride_time',
            'total_seats',
            'available_seats',
            'price_per_person',  
            'total_amount',      
            'notes',
            'vehicle_model',
            'driver_username',
            'driver_profile',
        ]

    def get_driver_profile(self, obj):
        request = self.context.get("request")
        if obj.ride.driver.profile and request:
            return request.build_absolute_uri(obj.ride.driver.profile.url)
        return None

    def get_requested_at(self, obj):
        return convert_to_ist(obj.requested_at)

    def get_total_amount(self, obj):
        return float(obj.ride.price_per_person) * obj.seats_requested
