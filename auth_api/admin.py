from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser,UserFCMToken

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser
    list_display = (
        'phone_number', 'username', 'role', 'is_active', 'is_staff', 'is_online', 'company'
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_online', 'driver_type', 'is_corporate_driver')

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        (_('Personal Info'), {
            'fields': (
                'username', 'email', 'gender', 'profile', 'dob', 'street', 'area', 'address_type', 'aadhar_card'
            )
        }),
        (_('Corporate Info'), {
            'fields': (
                'company', 'role', 'driver_type', 'is_universal_corporate_driver',
                'is_corporate_driver', 'corporate_companies', 'cash_payments_left'
            )
        }),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2', 'role'),
        }),
    )

    search_fields = ('phone_number', 'username', 'email')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions', 'corporate_companies')


admin.site.register(UserFCMToken)