from django.contrib import admin
from .models import PlatformSetting,RideReport


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ('fee_type', 'fee_value', 'is_active', 'updated_at')
    list_filter = ('fee_type', 'is_active')
    search_fields = ('fee_type',)


@admin.register(RideReport)
class RideReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'report_name', 'created_at')
    search_fields = ('report_name', 'description')
    list_filter = ('created_at',)