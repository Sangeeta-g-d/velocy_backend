from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from admin_part.models import SupportChat, SupportMessage, CustomUser
from datetime import datetime
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from notifications.fcm import send_fcm_notification

class SupportChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.group_name = f'support_chat_{self.chat_id}'
        self.admin_group_name = "support_admin"

        # Extract user from scope (session) first
        user = self.scope.get("user")

        # Parse JWT token from query string
        query_params = parse_qs(self.scope["query_string"].decode())
        token = query_params.get("token", [None])[0]

        if token:
            try:
                user_id = AccessToken(token)["user_id"]
                user = await database_sync_to_async(CustomUser.objects.get)(id=user_id)
                self.scope["user"] = user
            except Exception as e:
                print(f"[WS CONNECT] Invalid token: {e}")
                await self.close()
                return

        if not user or not user.is_authenticated:
            print("[WS CONNECT] Unauthorized connection attempt: user not authenticated.")
            await self.close()
            return

        # Admin chat (chat_id=0) requires staff user
        if self.chat_id == "0" and not user.is_staff:
            print("[WS CONNECT] Unauthorized admin access attempt.")
            await self.close()
            return

        # Regular user chat: verify ownership
        if self.chat_id != "0":
            try:
                chat = await database_sync_to_async(SupportChat.objects.get)(id=self.chat_id)
                if user.id != chat.user_id:
                    print(f"[WS CONNECT] User {user.id} trying to access chat {self.chat_id} (unauthorized).")
                    await self.close()
                    return
            except SupportChat.DoesNotExist:
                print(f"[WS CONNECT] Chat {self.chat_id} does not exist.")
                await self.close()
                return

        # Add user to channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Admins join separate group to receive all messages
        if self.chat_id == "0":
            await self.channel_layer.group_add(self.admin_group_name, self.channel_name)

        await self.accept()
        print(f"[WS CONNECT] User '{user.username}' connected to chat '{self.chat_id}'")

        
    async def disconnect(self, close_code):
        print(f"[WS DISCONNECT] Disconnected from chat '{self.chat_id}' with code {close_code}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if self.chat_id == "0":
            await self.channel_layer.group_discard(self.admin_group_name, self.channel_name)

    async def receive_json(self, content):
        print(f"[WS RECEIVE] Content: {content}")
        message_type = content.get("type")
        
        if message_type == "admin_reply":
            await self.handle_admin_reply(content)
        elif message_type == "user_message":
            await self.handle_user_message(content)
        else:
            print("[WS ERROR] Unknown message type received.")

    async def handle_admin_reply(self, content):
        """
        Handles messages sent by an admin.
        Saves the message and broadcasts it to both the user and admin groups.
        """
        message_text = content.get("message")
        chat_id = content.get("chat_id")
        user = self.scope.get("user")

        if not user.is_staff:
            print("[WS ERROR] Non-admin user attempted to send admin reply.")
            return

        try:
            # Get the chat and the admin user
            chat = await database_sync_to_async(SupportChat.objects.get)(id=chat_id)
            
            # Save the admin message to the database
            msg = await database_sync_to_async(SupportMessage.objects.create)(
                chat=chat, 
                user=user, 
                message=message_text, 
                is_admin=True
            )

            # Prepare data for broadcasting
            data = {
                "chat_id": str(chat.id),
                "sender_name": user.username,
                "sender_profile": user.profile.url if hasattr(user, 'profile') and user.profile else "/static/default-profile.png",
                "message": message_text,
                "is_admin": True,
                "timestamp": msg.created_at.isoformat(),
                "type": "admin_reply"
            }

            print(f"[WS BROADCAST] Admin reply: {data}")

            # Send the message to the specific chat group (for the user)
            await self.channel_layer.group_send(
                f'support_chat_{chat.id}',
                {"type": "support_message", "message": data}
            )

            # Send the message to the admin group (for other admins)
            await self.channel_layer.group_send(
                self.admin_group_name,
                {"type": "support_message", "message": data}
            )
                    # --- ✅ FCM Notification to user ---
            try:
                if chat.user:
                    from asgiref.sync import sync_to_async
                    await sync_to_async(send_fcm_notification)(
                        user=chat.user,
                        title="Support Reply 📨",
                        body=message_text,
                        data={
                            "chat_id": str(chat.id),
                            "type": "support_reply",
                            "sender_name": user.username
                        }
                    )
                    print(f"✅ FCM sent to user {chat.user.id}")
            except Exception as e:
                print(f"❌ Error sending FCM to user {chat.user.id}: {e}")
        except SupportChat.DoesNotExist:
            print(f"[ERROR] Chat {chat_id} does not exist for admin reply.")
        except Exception as e:
            print(f"[ERROR] Failed to handle admin reply: {e}")

    async def handle_user_message(self, content):
        """
        Handles messages sent by a user.
        Saves the message and broadcasts it to both the user and admin groups.
        """
        # This method's logic seems correct from your provided code, but I'll include it for completeness.
        message_text = content.get("message")
        chat_id = content.get("chat_id")
        user = self.scope.get("user")
        is_admin = content.get("is_admin", False)

        try:
            chat = await database_sync_to_async(SupportChat.objects.select_related('category', 'user').get)(id=chat_id)
            if not user or not user.is_authenticated or user.id != chat.user_id:
                 print("[WS ERROR] User mismatch or not authenticated for user message.")
                 return

            msg = await database_sync_to_async(SupportMessage.objects.create)(
                chat=chat, 
                user=user, 
                message=message_text, 
                is_admin=is_admin
            )

            profile_url = user.profile.url if hasattr(user, 'profile') and user.profile else "/static/default-profile.png"

            data = {
                "chat_id": str(chat.id),
                "sender_name": user.username,
                "sender_profile": profile_url,
                "message": message_text,
                "category_priority": chat.category.priority if chat.category else 0,
                "category_name": chat.category.name if chat.category else "General",
                "is_admin": is_admin,
                "timestamp": msg.created_at.isoformat(),
                "user_id": str(user.id),
                "type": "user_message"
            }

            print(f"[WS BROADCAST] User message: {data}")

            await self.channel_layer.group_send(
                f'support_chat_{chat_id}',
                {"type": "support_message", "message": data}
            )

            await self.channel_layer.group_send(
                self.admin_group_name,
                {"type": "support_message", "message": data}
            )

        except SupportChat.DoesNotExist:
            print(f"[ERROR] Chat {chat_id} does not exist.")
        except Exception as e:
            print(f"[ERROR] Failed to handle user message: {e}")

    async def support_message(self, event):
        """Send message to WebSocket client"""
        print(f"[WS SEND TO CLIENT] {event['message']}")
        await self.send_json(event["message"])