from rest_framework import serializers
from admin_part.models import SupportCategory

class SupportCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportCategory
        fields = ['id', 'name', 'priority', 'description']
