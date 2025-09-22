from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated  # optional, depending on your use-case
from admin_part.models import SupportCategory,SupportChat,SupportMessage
from .serializers import *
from rest_framework import status
from asgiref.sync import async_to_sync
import pytz
from channels.layers import get_channel_layer

class SupportCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]  # optional, you can allow any user

    def get(self, request):
        categories = SupportCategory.objects.all().order_by('priority', 'name')
        serializer = SupportCategorySerializer(categories, many=True)
        return Response({
            "status": True,
            "message": "Support categories fetched successfully",
            "data": serializer.data
        })



class StartOrGetSupportChatAPIView(APIView):
    """
    Get an existing active chat for the user & category, or create a new one.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        category_id = request.data.get('category_id')

        if not category_id:
            return Response({"status": False, "message": "Category ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            category = SupportCategory.objects.get(id=category_id)
        except SupportCategory.DoesNotExist:
            return Response({"status": False, "message": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if an active chat already exists for this user & category
        chat, created = SupportChat.objects.get_or_create(
            user=request.user,
            category=category,
            is_active=True
        )

        serializer = SupportChatSerializer(chat)
        return Response({
            "status": True,
            "message": "Chat retrieved." if not created else "Chat created.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    
class SendSupportMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        chat_id = request.data.get('chat_id')
        message_text = request.data.get('message')

        if not chat_id or not message_text:
            return Response({"status": False, "message": "Chat ID and message are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chat = SupportChat.objects.select_related('category', 'user').get(id=chat_id, is_active=True)
        except SupportChat.DoesNotExist:
            return Response({"status": False, "message": "Active chat not found."}, status=status.HTTP_404_NOT_FOUND)

        message = SupportMessage.objects.create(
            chat=chat,
            user=request.user,
            message=message_text,
            is_admin=False
        )

        # Get user profile URL
        profile_url = ""
        if request.user.profile:
            profile_url = request.user.profile.url
        else:
            profile_url = "/static/default-profile.png"

        # Prepare WebSocket data
        ws_data = {
            "chat_id": str(chat.id),
            "sender_name": request.user.username,
            "sender_profile": profile_url,
            "message": message_text,
            "category_priority": chat.category.priority if chat.category else 0,
            "category_name": chat.category.name if chat.category else "General",
            "is_admin": False,
            "timestamp": message.created_at.isoformat(),
            "user_id": str(request.user.id),
            "type": "user_message"
        }

        # Broadcast via WebSocket to admin group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'support_admin',  # Admin group
            {
                'type': 'support.message',
                'message': ws_data
            }
        )

        # Also send to the specific chat group
        async_to_sync(channel_layer.group_send)(
            f'support_chat_{chat.id}',
            {
                'type': 'support.message',
                'message': ws_data
            }
        )

        serializer = SupportMessageSerializer(message)
        return Response({"status": True, "message": "Message sent.", "data": serializer.data}, status=status.HTTP_201_CREATED)
    
class UserSupportChatHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        ist = pytz.timezone("Asia/Kolkata")

        # Get active chat or latest chat
        chat = SupportChat.objects.filter(user=user, is_active=True).first()
        if not chat:
            return Response({
                "chat_exists": False,
                "messages": []
            })

        # Get messages ordered by time (latest first)
        messages = SupportMessage.objects.filter(chat=chat).order_by("-created_at")

        history = []
        for msg in messages:
            sender = "Admin" if msg.is_admin else "You"

            # Convert UTC → IST
            created_at_ist = msg.created_at.astimezone(ist)

            # Format nicely
            formatted_time = created_at_ist.strftime("%d %b %Y, %I:%M %p")

            history.append({
                "id": msg.id,
                "sender": sender,
                "message": msg.message,
                "timestamp": formatted_time
            })

        return Response({
            "chat_exists": True,
            "chat_id": chat.id,
            "messages": history
        })