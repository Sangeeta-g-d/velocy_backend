from django.contrib import admin
from .models import PlatformSetting


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ('fee_type', 'fee_value', 'is_active', 'updated_at')
    list_filter = ('fee_type', 'is_active')
    search_fields = ('fee_type',)
