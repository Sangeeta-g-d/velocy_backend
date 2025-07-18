from rest_framework import serializers
from .models import RideShareVehicle,RideShareBooking,RideShareStop,RideShareRouteSegment,RideJoinRequest
from ride_sharing.time_utils import convert_to_ist
from pytz import timezone as pytz_timezone
from datetime import datetime, timedelta
from auth_api.models import CustomUser
from django.utils import timezone
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
        exclude = ['user', 'status', 'created_at', 'price']  # price optional, distance required

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
        user = self.context['request'].user
        passengers = validated_data.get('passengers_count')
        distance_km = validated_data.get('distance_km')
        ride_time = validated_data.get('ride_time')

        validated_data['user'] = user
        validated_data['status'] = 'draft'
        validated_data['seats_remaining'] = passengers

        # === Calculate estimated arrival time ===
        AVG_SPEED_KMPH = 40  # Or make this configurable

        if distance_km and ride_time:
            try:
                travel_hours = float(distance_km) / AVG_SPEED_KMPH
                ride_datetime = datetime.combine(datetime.today(), ride_time)
                estimated_arrival = ride_datetime + timedelta(hours=travel_hours)
                validated_data['to_location_estimated_arrival_time'] = estimated_arrival.time()
            except Exception as e:
                print(f"[ERROR] Failed to calculate ETA: {e}")

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

class RideShareRouteSegmentSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = RideShareRouteSegment
        fields = ['id','from_stop', 'to_stop', 'distance_km', 'price']

    def get_price(self, obj):
        return int(round(obj.price))  # Return whole number
    
class RideShareRouteSegmentPriceUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate(self, data):
        if 'price' not in data:
            raise serializers.ValidationError("Price is required for update.")
        return data


class RideShareRouteSegmentBulkPriceUpdateSerializer(serializers.Serializer):
    segments = RideShareRouteSegmentPriceUpdateSerializer(many=True)


class RideReturnDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideShareBooking
        fields = [
            'is_return_ride',
            'return_date',
            'return_time',
            'return_price',
            'return_distance_km',
            'passenger_notes'
        ]
        read_only_fields = ['return_distance_km']  # calculated in `update`

    def validate(self, attrs):
        is_return = attrs.get('is_return_ride')

        if is_return:
            missing_fields = []
            for field in ['return_date', 'return_time', 'return_price']:
                if not attrs.get(field):
                    missing_fields.append(field)

            if missing_fields:
                raise serializers.ValidationError({
                    field: 'This field is required for return ride.' for field in missing_fields
                })

        return attrs

    def update(self, instance, validated_data):
        is_return = validated_data.get('is_return_ride', instance.is_return_ride)

        instance.is_return_ride = is_return
        instance.passenger_notes = validated_data.get('passenger_notes', instance.passenger_notes)

        if is_return:
            instance.return_date = validated_data.get('return_date')
            instance.return_time = validated_data.get('return_time')
            instance.return_price = validated_data.get('return_price')
            instance.return_distance_km = instance.distance_km  # auto copy
        else:
            instance.return_date = None
            instance.return_time = None
            instance.return_price = None
            instance.return_distance_km = None
        instance.status = 'published'

        instance.save()
        return instance
    

class RidePriceUpdateSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be a positive value.")
        return value

class RideShareBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideShareBooking
        fields = [
            'id', 'from_location', 'to_location',
            'ride_date', 'ride_time',
            'passengers_count', 'women_only',
            'distance_km', 'price',
            'is_return_ride', 'return_date', 'return_time', 'return_price',
            'status'
        ]

class RideShareStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideShareStop
        fields = ['id','order', 'stop_location', 'stop_lat', 'stop_lng','estimated_arrival_time']

class RideShareSegmentPriceSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = RideShareRouteSegment
        fields = ['from_stop', 'to_stop', 'distance_km', 'price']

    def get_price(self, obj):
        return int(round(obj.price))


class RideJoinRequestViewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    profile_url = serializers.SerializerMethodField()
    from_location = serializers.SerializerMethodField()
    to_location = serializers.SerializerMethodField()
    created_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'id', 'username', 'profile_url', 'seats_requested',
            'status', 'message', 'created_at_ist',
            'from_location', 'to_location',
        ]

    def get_profile_url(self, obj):
        if obj.user.profile and hasattr(obj.user.profile, 'url'):
            return obj.user.profile.url
        return None

    def get_from_location(self, obj):
        if obj.segment:
            return obj.segment.from_stop
        return obj.ride.from_location

    def get_to_location(self, obj):
        if obj.segment:
            return obj.segment.to_stop
        return obj.ride.to_location

    def get_created_at_ist(self, obj):
    
        return convert_to_ist(obj.created_at)
    

class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'profile']

class RideJoinRequestDetailSerializer(serializers.ModelSerializer):
    rider = RiderProfileSerializer(source='ride.user', read_only=True)
    vehicle_name = serializers.CharField(source='ride.vehicle.model_name', read_only=True)
    from_location = serializers.SerializerMethodField()
    to_location = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    ride_status = serializers.SerializerMethodField()  # ✅ Add this field

    class Meta:
        model = RideJoinRequest
        fields = [
            'id',
            'from_location',
            'to_location',
            'rider',
            'vehicle_name',
            'seats_requested',
            'status',
            'message',
            'created_at',
            'ride_status',  # ✅ Include in output
        ]

    def get_from_location(self, obj):
        return obj.segment.from_stop if obj.segment else obj.ride.from_location

    def get_to_location(self, obj):
        return obj.segment.to_stop if obj.segment else obj.ride.to_location

    def get_created_at(self, obj):
        return convert_to_ist(obj.created_at)

    def get_ride_status(self, obj):
        ride = obj.ride
        now = timezone.localtime()
        ride_datetime = datetime.combine(ride.ride_date, ride.ride_time)
        ride_datetime = timezone.make_aware(ride_datetime, timezone.get_current_timezone())

        # Priority check
        if ride.status == 'cancelled':
            return 'cancelled'
        elif ride.status == 'completed':
            return 'completed'
        elif ride.status == 'in_progress':
            return 'in_progress'
        elif ride.status == 'published':
            if ride_datetime > now:
                return 'upcoming'
            elif ride_datetime <= now:
                return 'in_progress'

        return ride.status  # fallback

class AcceptedJoinRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    profile = serializers.SerializerMethodField()
    requested_at_ist = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    from_stop = serializers.SerializerMethodField()
    to_stop = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'username', 'profile', 'requested_at_ist',
            'seats_requested', 'status', 'total_price',
            'from_stop', 'to_stop',
        ]

    def get_profile(self, obj):
        return obj.user.profile.url if obj.user.profile else None

    def get_requested_at_ist(self, obj):
        return convert_to_ist(obj.created_at)

    def get_total_price(self, obj):
        if obj.segment:
            return float(obj.segment.price) * obj.seats_requested
        elif obj.ride.price:
            return float(obj.ride.price) * obj.seats_requested
        return 0.0

    def get_from_stop(self, obj):
        if obj.segment:
            return obj.segment.from_stop
        return obj.ride.from_location

    def get_to_stop(self, obj):
        if obj.segment:
            return obj.segment.to_stop
        return obj.ride.to_location
