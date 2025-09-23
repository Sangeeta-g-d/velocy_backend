from django.contrib import admin
from .models import RideSharePriceSetting,RideShareBooking

@admin.register(RideSharePriceSetting)
class RideSharePriceSettingAdmin(admin.ModelAdmin):
    list_display = ('min_price_per_km', 'max_price_per_km')
    list_display_links = ('min_price_per_km', 'max_price_per_km')  # Makes both fields clickable for editing

admin.site.register(RideShareBooking)