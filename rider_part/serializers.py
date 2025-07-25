from rest_framework import serializers
from admin_part.models import VehicleType
from . models import *
from admin_part.models import City
from django.utils.timezone import localtime
import pytz
from auth_api.models import DriverVehicleInfo, CustomUser
from admin_part.models import RideReport


class VehicleTypeSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'number_of_passengers', 'image']

class RideRequestCreateSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(write_only=True)
    ride_type = serializers.ChoiceField(choices=RideRequest.RIDE_TYPE_CHOICES)
    scheduled_time = serializers.DateTimeField(required=False, allow_null=True)
    ride_purpose = serializers.ChoiceField(
        choices=RideRequest.RIDE_PURPOSE_CHOICES,
        default='personal',
        required=False
    )

    class Meta:
        model = RideRequest
        fields = [
            'id',
            'ride_type',
            'scheduled_time',
            'city_name',
            'ride_purpose',  # ✅ added here
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

    def validate(self, attrs):
        ride_type = attrs.get('ride_type')
        scheduled_time = attrs.get('scheduled_time')
        ride_purpose = attrs.get('ride_purpose', 'personal')  # default is personal

        if ride_type == 'scheduled' and not scheduled_time:
            raise serializers.ValidationError({
                'scheduled_time': 'This field is required when ride_type is scheduled.'
            })
    
        request = self.context.get('request')
        user = request.user if request else None

        if ride_purpose == 'official':
            if not user or user.role != 'employee':
                raise serializers.ValidationError({
                    'ride_purpose': 'Only employees can create an official ride.'
                })

            if not user.company:
                raise serializers.ValidationError({
                    'ride_purpose': 'You are not assigned to any corporate company. Contact your administrator.'
                })

        return attrs

    

    def create(self, validated_data):
        city = validated_data.pop('city_name')
        user = self.context['request'].user
        company = getattr(user, 'company', None)

        return RideRequest.objects.create(
            user=user,
            city=city,
            company=company,
            status='draft',
            **validated_data
        )


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


class DriverVehicleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverVehicleInfo
        fields = ['vehicle_number', 'car_company', 'car_model']

class DriverSerializer(serializers.ModelSerializer):
    vehicle_info = DriverVehicleInfoSerializer(read_only=True)
    average_rating = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['username', 'profile', 'phone_number', 'vehicle_info', 'average_rating']

    def get_average_rating(self, obj):
        ratings = obj.received_ratings.all()
        if ratings.exists():
            return round(sum([r.rating for r in ratings]) / ratings.count(), 1)
        return 0.0

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.profile and hasattr(obj.profile, 'url'):
            return request.build_absolute_uri(obj.profile.url) if request else obj.profile.url
        return None


class RideDetailSerializer(serializers.ModelSerializer):
    driver = DriverSerializer()
    ride_stops = RideStopSerializer(many=True)

    class Meta:
        model = RideRequest
        fields = ['from_location', 'to_location', 'driver', 'ride_stops']


class DriverInfoSerializer(serializers.Serializer):
    name = serializers.CharField(source='driver.username')
    profile = serializers.ImageField(source='driver.profile')
    avg_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    vehicle_number = serializers.CharField()
    vehicle_name = serializers.CharField()


class RideStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideStop
        fields = '__all__'
        read_only_fields = ['order']

class RideRouteSerializer(serializers.ModelSerializer):
    stops = RideStopSerializer(source='ride_stops', many=True)

    class Meta:
        model = RideRequest
        fields = [
            'from_location', 'from_latitude', 'from_longitude',
            'to_location', 'to_latitude', 'to_longitude',
            'stops','ride_purpose'
        ]

class RideSummaryFormattedSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = [
            'start_time',
            'end_time',
            'price',
            'distance_km',
            'duration',
        ]

    def get_price(self, obj):
        return obj.offered_price if obj.offered_price else obj.estimated_price

    def get_start_time(self, obj):
        if obj.start_time:
            return obj.start_time.astimezone(pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
        return None

    def get_end_time(self, obj):
        if obj.end_time:
            return obj.end_time.astimezone(pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
        return None

    def get_duration(self, obj):
        if obj.start_time and obj.end_time:
            duration = obj.end_time - obj.start_time
            total_minutes = int(duration.total_seconds() // 60)
            hours, minutes = divmod(total_minutes, 60)
            return f"{hours} hours {minutes} minutes"
        return None


# ride history
class RiderRideHistorySerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = [
            'id', 'from_location', 'to_location',
            'date', 'start_time', 'amount_paid'
        ]

    def get_date(self, obj):
        if obj.start_time:
            ist = pytz.timezone("Asia/Kolkata")
            ist_time = obj.start_time.astimezone(ist)
            today = timezone.now().astimezone(ist).date()
            ride_date = ist_time.date()

            if ride_date == today:
                return "Today"
            elif ride_date == (today - timedelta(days=1)):
                return "Yesterday"
            return ist_time.strftime('%Y-%m-%d')
        return None

    def get_start_time(self, obj):
        if obj.start_time:
            ist_time = obj.start_time.astimezone(pytz.timezone("Asia/Kolkata"))
            return ist_time.strftime('%I:%M %p')
        return None

    def get_amount_paid(self, obj):
        payment = getattr(obj, 'payment_detail', None)
        if payment:
            return float(payment.grand_total)
        return 0.0
    

class RiderScheduledRideSerializer(serializers.ModelSerializer):
    scheduled_date = serializers.SerializerMethodField()
    scheduled_time = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = ['id', 'from_location', 'to_location', 'scheduled_date', 'scheduled_time']

    def get_scheduled_date(self, obj):
        if obj.scheduled_time:
            ist_time = obj.scheduled_time.astimezone(pytz.timezone("Asia/Kolkata"))
            return ist_time.strftime('%Y-%m-%d')
        return None

    def get_scheduled_time(self, obj):
        if obj.scheduled_time:
            ist_time = obj.scheduled_time.astimezone(pytz.timezone("Asia/Kolkata"))
            return ist_time.strftime('%I:%M %p')
        return None


class RiderProfileSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'profile']

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.profile and request:
            return request.build_absolute_uri(obj.profile.url)
        return None
    

class RideReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideReport
        fields = '__all__'


class RideReportSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideReportSubmission
        fields = ['id', 'ride', 'report_type', 'message', 'submitted_at']
        read_only_fields = ['id', 'submitted_at']


class FavoriteToLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteToLocation
        fields = ['id', 'name', 'to_location', 'to_latitude', 'to_longitude']