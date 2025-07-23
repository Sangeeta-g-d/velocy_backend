# consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import asyncio
import logging
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import RideMessage
from .models import RideRequest
logger = logging.getLogger(__name__)

class RideTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.group_name = f'ride_{self.ride_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        latitude = data['latitude']
        longitude = data['longitude']

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'send_location',
                'latitude': latitude,
                'longitude': longitude,
            }
        )

    async def send_location(self, event):
        await self.send(text_data=json.dumps({
            'latitude': event['latitude'],
            'longitude': event['longitude'],
        }))

# driver arrival notification consumer
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

            # Optional: Validate the ride or driver
            ride = await self.get_ride(ride_id)
            if ride:
                # Send notification to group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'arrival_notification',
                        'message': msg,
                        'ride_id': ride_id
                    }
                )

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
class RideNotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        print("Connected:", self.scope["path"])  # Debug print
        self.user = self.scope["user"]
        self.group_name = "ride_user_test"  # Or something dynamic if needed
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        pass

    async def send_otp(self, event):
        await self.send_json({
            "type": "otp",
            "otp": event["otp"]
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
        self.group_name = f'payment_ride_{self.ride_id}'

        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # This consumer is push-only; clients don't need to send messages here.
        pass

    async def payment_status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'payment_status_update',
            'ride_id': self.ride_id,
            'payment_status': event['payment_status'],
            'message': event['message'],
        }))



class RideAcceptanceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_authenticated:
            self.group_name = f"user_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ WebSocket connected: user_{self.user.id}")
        else:
            print("❌ Unauthorized WebSocket attempt")
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        # Optional: Handle client messages (if needed)
        pass

    async def ride_accepted(self, event):
        await self.send_json({
            "type": "ride_accepted",
            "ride_id": event["ride_id"],
            "message": event["message"],
            "driver_name": event["driver_name"],
            "driver_id": event["driver_id"],
        })
    async def ride_cancelled(self, event):
        await self.send_json({
            "type": "ride_cancelled",
            "ride_id": event["ride_id"],
            "message": event["message"],
            "driver_name": event["driver_name"],
            "driver_id": event["driver_id"],
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
