# consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from channels.generic.websocket import AsyncJsonWebsocketConsumer
import asyncio
import logging
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import RideMessage
from .models import RideRequest
from auth_api.models import CustomUser
from velocy_backend.firebase_config import *
from firebase_admin import messaging
from django.core.exceptions import ObjectDoesNotExist
from notifications.fcm import send_fcm_notification
logger = logging.getLogger(__name__)

class RideTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.group_name = f'ride_{self.ride_id}'
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ WebSocket connected for ride {self.ride_id}")
        except Exception as e:
            print(f"❌ Error on connect: {e}")

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"⚠️ WebSocket disconnected for ride {self.ride_id}, code: {close_code}")
        except Exception as e:
            print(f"❌ Error on disconnect: {e}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            print(f"📍 Received location: {latitude}, {longitude}")

            if latitude is not None and longitude is not None:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'send_location',
                        'latitude': latitude,
                        'longitude': longitude,
                    }
                )
        except Exception as e:
            print(f"❌ Error in receive: {e}")

    async def send_location(self, event):
        try:
            await self.send(text_data=json.dumps({
                'type': 'location_update',
                'latitude': event['latitude'],
                'longitude': event['longitude'],
            }))
            print(f"➡️ Sent location update: {event['latitude']}, {event['longitude']}")
        except Exception as e:
            print(f"❌ Error sending location: {e}")


            
class RideRequestConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.room_group_name = f'ride_request_{self.ride_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive_json(self, content):
        message_type = content.get('type')

        if message_type == 'notify_arrival':
            ride_id = content.get('ride_id')
            msg = content.get('message')

            # Optional: Validate the ride
            ride = await self.get_ride(ride_id)
            if ride:
                # 1️⃣ Send WebSocket notification to group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'arrival_notification',
                        'message': msg,
                        'ride_id': ride_id
                    }
                )

                # 2️⃣ Send FCM push notification to the rider
                try:
                    if ride.user:
                        send_fcm_notification(
                            user=ride.user,
                            title="Driver Arrived 🚖",
                            body=msg,
                            data={
                                "ride_id": str(ride.id),
                                "type": "driver_arrival",
                            }
                        )
                        print(f"✅ FCM sent to rider {ride.user.id}")
                except Exception as e:
                    print(f"❌ Error sending FCM: {e}")

    async def arrival_notification(self, event):
        await self.send_json({
            'type': 'notify_arrival',
            'ride_id': event['ride_id'],
            'message': event['message']
        })

    @database_sync_to_async
    def get_ride(self, ride_id):
        try:
            return RideRequest.objects.get(id=ride_id)
        except RideRequest.DoesNotExist:
            return None

# OTP consumer for ride notifications
# OTP consumer for ride notifications
class RideNotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.group_name = f"ride_{self.ride_id}"

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ [CONNECTED] ride_id={self.ride_id}, joined group {self.group_name}")
        except Exception as e:
            print(f"❌ [CONNECT ERROR] {e}")
            await self.close()

    async def disconnect(self, close_code):
        print(f"🔌 [DISCONNECT] ride_id={self.ride_id}, code={close_code}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Optional: keep the connection open
        pass

    # ------------------------
    # Group event handlers
    # ------------------------

    async def send_otp(self, event):
        """Send OTP to the client"""
        print(f"📢 [EVENT send_otp] {event}")
        await self.send_json({
            "type": "otp",
            "ride_id": self.ride_id,
            "otp": event["otp"]
        })

    async def notify_otp_verified(self, event):
        """Notify the client that OTP has been verified"""
        print(f"📢 [EVENT notify_otp_verified] {event}")
        await self.send_json({
            "type": "notify_otp_verified",
            "ride_id": self.ride_id,
            "message": event["message"]
        })



class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.room_group_name = f'chat_{self.ride_id}'
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()  # Deny connection if unauthenticated
        else:
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')

        if not message:
            return

        sender = self.user
        ride_id = self.ride_id

        # Save message to DB
        success = await self.save_message(sender, ride_id, message)

        if success:
            # Broadcast message to all clients in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender': sender.username,
                }
            )
        else:
            # Optionally notify sender of failure
            await self.send(text_data=json.dumps({
                'error': 'Ride does not exist. Message not saved.'
            }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
        }))

    @database_sync_to_async
    def save_message(self, sender, ride_id, message):
        try:
            ride = RideRequest.objects.get(id=ride_id)
            RideMessage.objects.create(
                ride=ride,
                sender=sender,
                message=message,
                timestamp=timezone.now()
            )
            return True
        except RideRequest.DoesNotExist:
            logger.error(f"RideRequest with ID {ride_id} does not exist. Message from user {sender} was not saved.")
            return False
        

class RidePaymentStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.ride_type = self.scope['url_route']['kwargs']['ride_type']  # 'normal' or 'shared'

        # Use unique group name based on ride type
        self.group_name = f'payment_{self.ride_type}_ride_{self.ride_id}'

        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # No messages expected from clients
        pass

    async def payment_status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'payment_status_update',
            'ride_id': self.ride_id,
            'ride_type': self.ride_type,
            'payment_status': event['payment_status'],
            'message': event['message'],
        }))

# verify otp

class RideOTPConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.group_name = f"ride_otp_{self.ride_id}"

        await self.accept()
        print(f"✅ Connected to Ride OTP Channel: {self.group_name}")

        # Add this connection to the ride-specific group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        print(f"❌ Disconnected from Ride OTP Channel: {self.group_name}")

    # Handler for OTP verification event
    async def otp_verified(self, event):
        await self.send_json({
            "type": "notify_otp_verified",
            "ride_id": event.get("ride_id"),
            "message": event.get("message")
        })
# shared ride tracking consumer
class SharedRideTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.room_group_name = f'shared_ride_tracking_{self.ride_id}'

        # Join group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket (driver sends location updates)
    async def receive(self, text_data):
        data = json.loads(text_data)
        latitude = data['lat']
        longitude = data['lng']

        # Broadcast to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'send_location',
                'lat': latitude,
                'lng': longitude
            }
        )

    # Send location to WebSocket group
    async def send_location(self, event):
        await self.send(text_data=json.dumps({
            'lat': event['lat'],
            'lng': event['lng']
        }))



class SharedRideNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_authenticated:
            self.group_name = f"shared_ride_user_{user.id}"  # ✅ Updated group name
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def shared_ride_destination_reached(self, event):  # ✅ Updated method name
        await self.send(text_data=json.dumps({
            "type": "shared_ride_destination_reached",  # ✅ Updated event type
            "ride_id": event["ride_id"],
            "message": event["message"],
            "timestamp": event["timestamp"],
        }))


class RideCompletionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            self.ride_id = self.scope["url_route"]["kwargs"]["ride_id"]
            self.group_name = f"ride_{self.ride_id}"
            print(f"🔌 [CONNECT] ride_id={self.ride_id}, user={self.scope.get('user')}")

            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ [CONNECTED] Joined group {self.group_name}")

        except Exception as e:
            print(f"❌ [CONNECT ERROR] {e}")
            await self.close()

    async def disconnect(self, close_code):
        print(f"🔌 [DISCONNECT] ride_id={getattr(self, 'ride_id', None)}, "
              f"group={getattr(self, 'group_name', None)}, code={close_code}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ride_completed(self, event):
        print(f"📢 [EVENT ride_completed] {event}")
        await self.send_json({
            "type": "ride_completed",
            "ride_id": event["ride_id"],
            "message": event["message"],
            "end_time": event["end_time"]
        })

   
   


# ride sharing in emergency

class RideLocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.room_group_name = f"ride_session_{self.ride_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive location update from backend
    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            "latitude": event["latitude"],
            "longitude": event["longitude"],
            "recorded_at": event["recorded_at"],
        }))



# cancel ride web scoket
class RideCancellationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            # Get ride_id from URL
            self.ride_id = self.scope["url_route"]["kwargs"]["ride_id"]
            self.group_name = f"ride_cancellation_{self.ride_id}"  # rider group
            self.driver_group_name = f"ride_driver_{self.ride_id}"  # driver group

            # Add to rider group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            # Optionally, if driver connects too, they join driver group
            await self.channel_layer.group_add(self.driver_group_name, self.channel_name)

            await self.accept()
            print(f"✅ [CONNECT] WebSocket connected to ride_cancellation_{self.ride_id}")

        except Exception as e:
            print(f"❌ [CONNECT ERROR] {e}")
            await self.close()

    async def disconnect(self, close_code):
        print(f"🔌 [DISCONNECT] Leaving groups for ride {getattr(self, 'ride_id', None)}")
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "driver_group_name"):
            await self.channel_layer.group_discard(self.driver_group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        print(f"📩 [RECEIVE] From client: {content}")
        # Broadcast to rider group
        try:
            message = content.get("message", {})
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "ride_cancellation_message",
                    "message": message
                }
            )
            print(f"📢 [BROADCAST] Sent to rider group {self.group_name}: {message}")
        except Exception as e:
            print(f"❌ [RECEIVE ERROR] {e}")

    async def ride_cancellation_message(self, event):
        message = event.get("message", {})
        print(f"📤 [SEND] To client: {message}")
        await self.send_json({
            "type": "ride_cancellation",
            "message": message
        })

    # ------------------- New helper for driver -------------------
    @staticmethod
    def send_driver_notification(ride_id, message):
        """
        Use async_to_sync to send message to driver group from a view
        """
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"ride_driver_{ride_id}",
            {
                "type": "ride_cancellation_message",
                "message": message
            }
        )
        print(f"✅ WebSocket message sent to driver group ride_driver_{ride_id}")



# shared ride payment notification
class SharedRideDriverConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.driver_id = self.scope['url_route']['kwargs']['driver_id']
        self.group_name = f'driver_{self.driver_id}'

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def payment_notification(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'payment',
            'message': message
        }))

class SharedRideJoinerPaymentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.rider_id = self.scope['url_route']['kwargs']['rider_id']
        self.group_name = f"rider_{self.rider_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def cash_verified(self, event):
        await self.send(text_data=json.dumps({
            "type": "cash_verified",
            "message": event['message']
        }))

    async def payment_notification(self, event):
        await self.send(text_data=json.dumps({
            "type": "payment_notification",
            "message": event['message']
        }))
