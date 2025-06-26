from django.db import models
from auth_api.models import CustomUser
# Create your models here.

class FCMDevice(models.Model):
    DEVICE_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='fcm_devices')
    token = models.TextField()
    device_id = models.CharField(max_length=255, blank=True, null=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'device_id')
