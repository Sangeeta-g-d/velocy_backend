from rest_framework import serializers
from .models import RideShareVehicle,RideShareBooking,RideShareStop,RideShareRouteSegment,RideJoinRequest
from ride_sharing.time_utils import convert_to_ist
from pytz import timezone as pytz_timezone
from datetime import datetime, timedelta
from auth_api.models import DriverVehicleInfo
from auth_api.models import CustomUser
from decimal import Decimal
from django.utils import timezone
from .utils.travel import calculate_eta
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


# ride sharing booking serializer
class RideShareBookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideShareBooking
        exclude = ['user', 'status', 'created_at', 'price']

    def validate(self, attrs):
        distance = attrs.get('distance_km')
        print("[DEBUG] Distance received for validation:", distance)

        if not distance or distance <= 0:
            raise serializers.ValidationError("Distance must be a positive number.")
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        vehicle_id = self.initial_data.get('vehicle')
        passengers = validated_data.get('passengers_count')
    
        print(f"[DEBUG] Creating booking for user: {user} | Role: {user.role}")
        print(f"[DEBUG] Vehicle ID from initial data: {vehicle_id}")
        print(f"[DEBUG] Passengers count: {passengers}")
    
        if user.role == 'rider':
            try:
                vehicle_obj = RideShareVehicle.objects.get(id=vehicle_id)
            except RideShareVehicle.DoesNotExist:
                raise serializers.ValidationError("Vehicle does not exist.")
    
            validated_data['passengers_count'] = vehicle_obj.seat_capacity
            validated_data['seats_remaining'] = vehicle_obj.seat_capacity
    
        else:  # driver
            if not passengers:
                raise serializers.ValidationError("passengers_count is required for drivers.")
            seat_capacity = validated_data.get('seat_capacity')
            if seat_capacity and passengers > seat_capacity:
                raise serializers.ValidationError("Passenger count exceeds seat capacity.")
            validated_data['seats_remaining'] = passengers
    
        validated_data['user'] = user
        validated_data['status'] = 'draft'
    
        # ETA calculation
        distance_km = validated_data.get('distance_km')
        ride_time = validated_data.get('ride_time')
        AVG_SPEED_KMPH = 40
    
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
        exclude = ['user', 'status', 'created_at', 'price']

    def validate(self, attrs):
        distance = attrs.get('distance_km')

        if not distance or distance <= 0:
            raise serializers.ValidationError("Distance must be a positive number.")

        return attrs

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        vehicle_id = self.initial_data.get('vehicle')
        passengers = validated_data.get('passengers_count')

        # Fetch vehicle object
        try:
            vehicle_obj = RideShareVehicle.objects.get(id=vehicle_id)
        except RideShareVehicle.DoesNotExist:
            raise serializers.ValidationError("Vehicle does not exist.")

        if user.role == 'rider':
            validated_data['passengers_count'] = vehicle_obj.seat_capacity
        else:
            if not passengers:
                raise serializers.ValidationError("passengers_count is required for drivers.")
            if passengers > vehicle_obj.seat_capacity:
                raise serializers.ValidationError("Passenger count exceeds seat capacity.")

        validated_data['user'] = user
        validated_data['status'] = 'draft'
        validated_data['seats_remaining'] = validated_data['passengers_count']

        distance_km = validated_data.get('distance_km')
        ride_time = validated_data.get('ride_time')  # time object

        # Estimate arrival time if distance and time are provided
        if distance_km and ride_time:
            try:
                AVG_SPEED_KMPH = 40
                travel_hours = float(distance_km) / AVG_SPEED_KMPH

                # Combine today’s date with ride_time to form datetime
                today = datetime.today().date()
                ride_datetime = datetime.combine(today, ride_time)

                eta_datetime = ride_datetime + timedelta(hours=travel_hours)
                validated_data['to_location_estimated_arrival_time'] = eta_datetime.time()
            except Exception as e:
                print(f"[ETA ERROR] Failed to calculate ETA: {e}")

        return RideShareBooking.objects.create(**validated_data)
    

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
    from_time = serializers.SerializerMethodField()
    to_time = serializers.SerializerMethodField()
    from_lat = serializers.SerializerMethodField()
    from_lng = serializers.SerializerMethodField()
    to_lat = serializers.SerializerMethodField()
    to_lng = serializers.SerializerMethodField()
    created_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'id', 'username', 'profile_url',
            'seats_requested', 'status', 'message',
            'created_at_ist',
            'from_location', 'to_location',
            'from_time', 'to_time',
            'from_lat', 'from_lng',
            'to_lat', 'to_lng',
        ]

    def get_profile_url(self, obj):
        request = self.context.get('request')
        if obj.user.profile and hasattr(obj.user.profile, 'url'):
            return request.build_absolute_uri(obj.user.profile.url)
        return None

    def get_from_location(self, obj):
        return obj.segment.from_stop if obj.segment else obj.ride.from_location

    def get_to_location(self, obj):
        return obj.segment.to_stop if obj.segment else obj.ride.to_location

    def get_from_time(self, obj):
        ride = self.context.get('ride')
        if obj.segment:
            # find stop object with same location
            stop = RideShareStop.objects.filter(
                ride_booking=ride,
                stop_location__iexact=obj.segment.from_stop
            ).first()
            if stop and stop.estimated_arrival_time:
                return stop.estimated_arrival_time.strftime('%H:%M:%S')
        # fallback to ride start time
        return ride.ride_time.strftime('%H:%M:%S')

    def get_to_time(self, obj):
        ride = self.context.get('ride')
        if obj.segment:
            stop = RideShareStop.objects.filter(
                ride_booking=ride,
                stop_location__iexact=obj.segment.to_stop
            ).first()
            if stop and stop.estimated_arrival_time:
                return stop.estimated_arrival_time.strftime('%H:%M:%S')
            # if destination of ride
            if obj.segment.to_stop.lower() == ride.to_location.lower() and ride.to_location_estimated_arrival_time:
                return ride.to_location_estimated_arrival_time.strftime('%H:%M:%S')
        # fallback to ride destination arrival
        return ride.to_location_estimated_arrival_time.strftime('%H:%M:%S') if ride.to_location_estimated_arrival_time else None

    def get_from_lat(self, obj):
        ride = self.context.get('ride')
        if obj.segment:
            stop = RideShareStop.objects.filter(
                ride_booking=ride,
                stop_location__iexact=obj.segment.from_stop
            ).first()
            if stop:
                return stop.stop_lat
        # fallback to main ride start
        return ride.from_location_lat

    def get_from_lng(self, obj):
        ride = self.context.get('ride')
        if obj.segment:
            stop = RideShareStop.objects.filter(
                ride_booking=ride,
                stop_location__iexact=obj.segment.from_stop
            ).first()
            if stop:
                return stop.stop_lng
        return ride.from_location_lng

    def get_to_lat(self, obj):
        ride = self.context.get('ride')
        if obj.segment:
            stop = RideShareStop.objects.filter(
                ride_booking=ride,
                stop_location__iexact=obj.segment.to_stop
            ).first()
            if stop:
                return stop.stop_lat
        return ride.to_location_lat

    def get_to_lng(self, obj):
        ride = self.context.get('ride')
        if obj.segment:
            stop = RideShareStop.objects.filter(
                ride_booking=ride,
                stop_location__iexact=obj.segment.to_stop
            ).first()
            if stop:
                return stop.stop_lng
        return ride.to_location_lng

    def get_created_at_ist(self, obj):
        return convert_to_ist(obj.created_at)
    

class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'profile']

class RideJoinRequestDetailSerializer(serializers.ModelSerializer):
    rider = RiderProfileSerializer(source='ride.user', read_only=True)
    vehicle_name = serializers.SerializerMethodField()
    from_location = serializers.SerializerMethodField()
    to_location = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    ride_status = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    vehicle_info = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'id',
            'from_location',
            'to_location',
            'rider',
            'vehicle_name',
            'vehicle_info',
            'seats_requested',
            'status',
            'message',
            'created_at',
            'ride_status',
            'start_time',
            'end_time',
            'duration',
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

        return ride.status

    def get_vehicle_name(self, obj):
        ride = obj.ride
        creator = ride.user

        if creator.role == 'rider' and ride.vehicle:
            return ride.vehicle.model_name
        elif creator.role == 'driver':
            try:
                vehicle_info = creator.vehicle_info
                return f"{vehicle_info.car_company} {vehicle_info.car_model}"
            except DriverVehicleInfo.DoesNotExist:
                return None
        return None

    def get_vehicle_info(self, obj):
        ride = obj.ride
        creator = ride.user

        if creator.role == 'rider' and ride.vehicle:
            return {
                "model_name": ride.vehicle.model_name,
                "vehicle_number": ride.vehicle.vehicle_number,
                "seat_capacity": ride.vehicle.seat_capacity,
            }
        elif creator.role == 'driver':
            try:
                vehicle_info = creator.vehicle_info
                return {
                    "car_company": vehicle_info.car_company,
                    "car_model": vehicle_info.car_model,
                    "vehicle_number": vehicle_info.vehicle_number,
                    "vehicle_type": vehicle_info.vehicle_type,
                    "year": vehicle_info.year,
                }
            except DriverVehicleInfo.DoesNotExist:
                return None
        return None

    def get_start_time(self, obj):
        ride = obj.ride
        if obj.segment:
            from_stop = RideShareStop.objects.filter(ride_booking=ride, stop_location__icontains=obj.segment.from_stop).first()
            if from_stop:
                return from_stop.estimated_arrival_time.strftime('%H:%M:%S') if from_stop.estimated_arrival_time else None
        return ride.ride_time.strftime('%H:%M:%S') if ride.ride_time else None

    def get_end_time(self, obj):
        ride = obj.ride
        if obj.segment:
            to_stop = RideShareStop.objects.filter(ride_booking=ride, stop_location__icontains=obj.segment.to_stop).first()
            if to_stop:
                return to_stop.estimated_arrival_time.strftime('%H:%M:%S') if to_stop.estimated_arrival_time else None
        return ride.to_location_estimated_arrival_time.strftime('%H:%M:%S') if ride.to_location_estimated_arrival_time else None

    def get_duration(self, obj):
        from datetime import datetime, timedelta
        start_str = self.get_start_time(obj)
        end_str = self.get_end_time(obj)

        if start_str and end_str:
            fmt = '%H:%M:%S'
            try:
                start_dt = datetime.strptime(start_str, fmt)
                end_dt = datetime.strptime(end_str, fmt)
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                duration = end_dt - start_dt
                total_minutes = duration.total_seconds() // 60
                hours = int(total_minutes // 60)
                minutes = int(total_minutes % 60)
                return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            except:
                return None
        return None


class AcceptedJoinRequestSerializer(serializers.ModelSerializer):
    request_id = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    requested_at_ist = serializers.SerializerMethodField()
    from_stop = serializers.SerializerMethodField()
    to_stop = serializers.SerializerMethodField()
    from_lat = serializers.SerializerMethodField()
    from_lng = serializers.SerializerMethodField()
    to_lat = serializers.SerializerMethodField()
    to_lng = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = RideJoinRequest
        fields = [
            'request_id', 'username', 'phone_number', 'profile', 'requested_at_ist',
            'seats_requested', 'status', 'total_price',
            'from_stop', 'to_stop', 'from_lat', 'from_lng', 'to_lat', 'to_lng'
        ]

    def get_request_id(self, obj):
        return obj.id

    def get_username(self, obj):
        return obj.user.username

    def get_phone_number(self, obj):
        return obj.user.phone_number

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.user.profile and hasattr(obj.user.profile, 'url'):
            return request.build_absolute_uri(obj.user.profile.url)
        return None

    def get_requested_at_ist(self, obj):
        return obj.created_at.astimezone().strftime("%Y-%m-%d %I:%M %p")

    def get_from_stop(self, obj):
        return obj.segment.from_stop if obj.segment else obj.ride.from_location

    def get_to_stop(self, obj):
        return obj.segment.to_stop if obj.segment else obj.ride.to_location

    def get_from_lat(self, obj):
        if obj.segment:
            stop_name = obj.segment.from_stop
            if stop_name == obj.ride.from_location:
                return obj.ride.from_location_lat
            stop = obj.ride.stops.filter(stop_location=stop_name).first()
            return stop.stop_lat if stop else None
        return obj.ride.from_location_lat

    def get_from_lng(self, obj):
        if obj.segment:
            stop_name = obj.segment.from_stop
            if stop_name == obj.ride.from_location:
                return obj.ride.from_location_lng
            stop = obj.ride.stops.filter(stop_location=stop_name).first()
            return stop.stop_lng if stop else None
        return obj.ride.from_location_lng

    def get_to_lat(self, obj):
        if obj.segment:
            stop_name = obj.segment.to_stop
            if stop_name == obj.ride.to_location:
                return obj.ride.to_location_lat
            stop = obj.ride.stops.filter(stop_location=stop_name).first()
            return stop.stop_lat if stop else None
        return obj.ride.to_location_lat

    def get_to_lng(self, obj):
        if obj.segment:
            stop_name = obj.segment.to_stop
            if stop_name == obj.ride.to_location:
                return obj.ride.to_location_lng
            stop = obj.ride.stops.filter(stop_location=stop_name).first()
            return stop.stop_lng if stop else None
        return obj.ride.to_location_lng

    def get_total_price(self, obj):
        return obj.segment.price if obj.segment else obj.ride.price

class RatingSerializer(serializers.Serializer):
    rating = serializers.DecimalField(
        max_digits=2,
        decimal_places=1,
        min_value=Decimal('0.0'),  
        max_value=Decimal('5.0')   
    )