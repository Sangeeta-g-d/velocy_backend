from django.contrib import admin
from .models import CompanyAccount

@admin.register(CompanyAccount)
class CompanyAccountAdmin(admin.ModelAdmin):
    list_display = (
        'company_name', 'admin_user', 'business_registration_number',
        'gst_number', 'city', 'is_approved', 'purchased_plan', 'created_at'
    )
    list_filter = ('is_approved', 'purchased_plan', 'city')
    search_fields = ('company_name', 'business_registration_number', 'gst_number', 'admin_user__phone_number')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['admin_user']
