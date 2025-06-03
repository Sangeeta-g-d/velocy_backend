from django.db import models

# Create your models here.

class City(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class VehicleType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    number_of_passengers = models.PositiveIntegerField(
        help_text="Maximum number of passengers allowed", default=1
    )
    image = models.ImageField(
        upload_to='vehicle_types/',
        blank=True,
        null=True,
        help_text="Upload an image representing this vehicle type"
    )

    def __str__(self):
        return f"{self.name} ({self.number_of_passengers} passengers)"
    
class CityVehiclePrice(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='vehicle_prices')
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE, related_name='city_prices')
    price_per_km = models.DecimalField(max_digits=6, decimal_places=2)  # ₹/km

    class Meta:
        unique_together = ('city', 'vehicle_type')  # Avoid duplicates

    def __str__(self):
        return f"{self.city.name} - {self.vehicle_type.name}: ₹{self.price_per_km}/km"
