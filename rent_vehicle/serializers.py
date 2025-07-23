from rest_framework import serializers
from .models import RentedVehicle, RentedVehicleImage,RentalRequest,HandoverChecklist
from auth_api.models import CustomUser
from django.utils import timezone
import pytz
from django.db.models import Avg

class RentedVehicleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentedVehicleImage
        fields = ['id', 'image', 'uploaded_at']

class RentedVehicleCreateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=True
    )

    class Meta:
        model = RentedVehicle
        fields = [
            'vehicle_name', 'vehicle_type', 'registration_number',
            'seating_capacity', 'fuel_type', 'transmission', 'security_deposite', # Added comma here
            'rental_price_per_hour', 'available_from_date', 'available_to_date',
            'pickup_location', 'vehicle_papers_document', 'confirmation_checked',
            'vehicle_color', 'is_ac', 'is_available', 'images','bag_capacity'
        ]

    def create(self, validated_data):
        images = validated_data.pop('images')
        user = self.context['request'].user
        rented_vehicle = RentedVehicle.objects.create(user=user, **validated_data)

        for image in images:
            RentedVehicleImage.objects.create(vehicle=rented_vehicle, image=image)

        return rented_vehicle

    def create(self, validated_data):
        images = validated_data.pop('images')
        user = self.context['request'].user
        rented_vehicle = RentedVehicle.objects.create(user=user, **validated_data)

        for image in images:
            RentedVehicleImage.objects.create(vehicle=rented_vehicle, image=image)

        return rented_vehicle


class UserRentedVehicleListSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    class Meta:
        model = RentedVehicle
        fields = ['id', 'vehicle_name', 'registration_number', 'vehicle_color', 'is_approved', 'images']

    def get_images(self, obj):
        return [image.image.url for image in obj.images.all()]
    
class RentedVehicleEditImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentedVehicleImage
        fields = ['id', 'image', 'uploaded_at']


# edit serializer
class RentedVehicleEditSerializer(serializers.ModelSerializer):
    images = RentedVehicleImageSerializer(many=True, read_only=True)

    class Meta:
        model = RentedVehicle
        fields = [
            'id', 'vehicle_name', 'vehicle_type', 'registration_number', 'seating_capacity',
            'fuel_type', 'transmission', 'rental_price_per_hour', 'available_from_date',
            'available_to_date', 'pickup_location', 'vehicle_papers_document',
            'confirmation_checked', 'vehicle_color', 'is_ac', 'is_available',
            'is_approved', 'images','security_deposite'
        ]


class RentedVehicleHomeScreenListSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    class Meta:
        model = RentedVehicle
        fields = [
            'id',
            'vehicle_name',
            'vehicle_type',
            'seating_capacity',
            'rental_price_per_hour',
            'is_available',
            'images',
            'bag_capacity',
        ]

    def get_images(self, obj):
        return [img.image.url for img in obj.images.all()]
    


# rental car details
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'profile']


class RentedVehicleDetailSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    user = UserProfileSerializer()

    class Meta:
        model = RentedVehicle
        fields = [
            'id', 'vehicle_name', 'vehicle_type', 'rental_price_per_hour',
            'seating_capacity', 'is_ac', 'fuel_type', 'transmission','pickup_location',
            'images', 'average_rating', 'user'
        ]

    def get_images(self, obj):
        return [img.image.url for img in obj.images.all()]

    def get_average_rating(self, obj):
        avg = obj.ratings.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else None
    
class VehicleOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'phone_number', 'profile', 'aadhar_card']


class RentedVehicleOwnerDetailSerializer(serializers.ModelSerializer):
    user = VehicleOwnerSerializer()
    images = serializers.SerializerMethodField()

    class Meta:
        model = RentedVehicle
        fields = [
            'vehicle_name', 'registration_number', 'rental_price_per_hour',
            'vehicle_color', 'vehicle_papers_document', 'user', 'images'
        ]

    def get_images(self, obj):
        return [img.image.url for img in obj.images.all()]
    
class RentalRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalRequest
        fields = ['pickup_datetime', 'dropoff_datetime', 'license_document']

    def create(self, validated_data):
        request = self.context['request']
        vehicle = self.context['vehicle']
        user = request.user
        lessor = vehicle.user

        # Now safely create the RentalRequest
        return RentalRequest.objects.create(
            user=user,
            vehicle=vehicle,
            lessor=lessor,
            **validated_data
        )

class RentalRequestListSerializer(serializers.ModelSerializer):
    lessor_username = serializers.CharField(source='lessor.username', read_only=True)
    lessor_profile = serializers.ImageField(source='lessor.profile_image', read_only=True)

    vehicle_name = serializers.CharField(source='vehicle.vehicle_name', read_only=True)
    registration_number = serializers.CharField(source='vehicle.registration_number', read_only=True)

    pickup = serializers.SerializerMethodField()
    dropoff = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'id',
            'status',
            'lessor_username',
            'lessor_profile',
            'vehicle_name',
            'registration_number',
            'pickup',
            'dropoff',
            'duration_hours'
        ]

    def get_pickup(self, obj):
        return obj.pickup_datetime.strftime('%d %b %Y, %I:%M %p')  # e.g., "12 Jun 2025, 10:00 AM"

    def get_dropoff(self, obj):
        return obj.dropoff_datetime.strftime('%d %b %Y, %I:%M %p')


class LessorRentalRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_profile = serializers.ImageField(source='user.profile', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)

    vehicle_name = serializers.CharField(source='vehicle.vehicle_name', read_only=True)
    registration_number = serializers.CharField(source='vehicle.registration_number', read_only=True)
    vehicle_color = serializers.CharField(source='vehicle.vehicle_color', read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'id',
            'username',
            'user_profile',
            'phone_number',
            'vehicle_name',
            'registration_number',
            'vehicle_color',
            'status'
        ]

class RentalRequestDetailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    profile = serializers.SerializerMethodField()
    area = serializers.CharField(source='user.area', read_only=True)
    street = serializers.CharField(source='user.street', read_only=True)
    aadhar_card = serializers.SerializerMethodField()
    vehicle_name = serializers.CharField(source='vehicle.vehicle_name', read_only=True)
    driving_license = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'id',
            'username',
            'phone_number',
            'profile',
            'area',
            'street',
            'driving_license',
            'vehicle_name',
            'aadhar_card',
        ]

    def get_profile(self, obj):
        request = self.context.get('request')
        if obj.user.profile:
            return request.build_absolute_uri(obj.user.profile.url) if request else obj.user.profile.url
        return None

    def get_driving_license(self, obj):
        request = self.context.get('request')
        if obj.license_document:
            return request.build_absolute_uri(obj.license_document.url) if request else obj.license_document.url
        return None

    def get_aadhar_card(self, obj):
        request = self.context.get('request')
        if obj.user.aadhar_card:
            return request.build_absolute_uri(obj.user.aadhar_card.url) if request else obj.user.aadhar_card.url
        return None
    

class RentalRequestVehicleInfoSerializer(serializers.ModelSerializer):
    vehicle_name = serializers.CharField(source='vehicle.vehicle_name', read_only=True)
    vehicle_image = serializers.SerializerMethodField()
    total_rent_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    security_deposite = serializers.DecimalField(source='vehicle.security_deposite', max_digits=10, decimal_places=2, read_only=True)
    license_document = serializers.FileField(read_only=True)

    class Meta:
        model = RentalRequest
        fields = [
            'id',
            'vehicle_name',
            'vehicle_image',
            'license_document',
            'total_rent_price',
            'security_deposite',
        ]

    def get_vehicle_image(self, obj):
        first_image = obj.vehicle.images.first()
        if first_image:
            request = self.context.get('request')
            return request.build_absolute_uri(first_image.image.url) if request else first_image.image.url
        return None
    

class HandoverChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverChecklist
        fields = [
            'handed_over_car_keys',
            'handed_over_vehicle_documents',
            'fuel_tank_full'
        ]

class HandoverChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverChecklist
        fields = ['handed_over_car_keys', 'handed_over_vehicle_documents', 'fuel_tank_full', 'checklist_completed_at']


class RentalHandoverDetailSerializer(serializers.ModelSerializer):
    vehicle_name = serializers.CharField(source='vehicle.vehicle_name', read_only=True)
    registration_number = serializers.CharField(source='vehicle.registration_number', read_only=True)
    security_deposite = serializers.DecimalField(source='vehicle.security_deposite', max_digits=10, decimal_places=2, read_only=True)

    handed_over_car_keys = serializers.BooleanField(source='handover_checklist.handed_over_car_keys', read_only=True)
    handed_over_vehicle_documents = serializers.BooleanField(source='handover_checklist.handed_over_vehicle_documents', read_only=True)
    fuel_tank_full = serializers.BooleanField(source='handover_checklist.fuel_tank_full', read_only=True)
    checklist_completed_at = serializers.SerializerMethodField()

    class Meta:
        model = RentalRequest
        fields = [
            'vehicle_name', 'registration_number', 'total_rent_price', 'security_deposite',
            'handed_over_car_keys', 'handed_over_vehicle_documents',
            'fuel_tank_full', 'checklist_completed_at'
        ]

    def get_checklist_completed_at(self, obj):
        dt = obj.handover_checklist.checklist_completed_at
        if dt:
            ist = pytz.timezone('Asia/Kolkata')
            dt_ist = dt.astimezone(ist)
            return dt_ist.strftime('%d-%m-%Y %I:%M %p')
        return None