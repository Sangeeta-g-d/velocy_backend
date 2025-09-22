from rest_framework import serializers
from admin_part.models import SupportCategory,SupportChat,SupportMessage

class SupportCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportCategory
        fields = ['id', 'name', 'priority', 'description']


class SupportCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportCategory
        fields = ['id', 'name', 'priority', 'description']

class SupportChatSerializer(serializers.ModelSerializer):
    category = SupportCategorySerializer()  # Nested category info

    class Meta:
        model = SupportChat
        fields = ['id', 'category', 'is_active', 'created_at']


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='user.username', read_only=True)
    sender_profile = serializers.ImageField(source='user.profile', read_only=True)
    category_priority = serializers.IntegerField(source='chat.category.priority', read_only=True)

    class Meta:
        model = SupportMessage
        fields = ['id', 'chat', 'user', 'message', 'is_admin', 'created_at', 'sender_name', 'sender_profile', 'category_priority']
        read_only_fields = ['id', 'created_at', 'is_admin', 'sender_name', 'sender_profile', 'category_priority']