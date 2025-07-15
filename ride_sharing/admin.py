from django.contrib import admin
from . models import RideSharePriceSetting

# Register your models here.
@admin.register(RideSharePriceSetting)
class RideSharePriceSettingAdmin(admin.ModelAdmin):
    list_display = ('price_per_km', 'effective_from')
    ordering = ('-effective_from',)