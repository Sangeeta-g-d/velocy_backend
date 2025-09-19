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
from auth_api.models import CustomUser
from django.core.exceptions import ObjectDoesNotExist
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
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        self.group_name = f"ride_{self.ride_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # make sure you remove the user from the group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """
        Optional: keeps the connection open even if the client
        never sends anything. You can just pass for now.
        """
        pass

    # <--- these are group event handlers (they must be flat methods) ----->

    async def send_otp(self, event):
        await self.send_json({
            "type": "otp",
            "ride_id": self.ride_id,
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


class RideAcceptanceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            # Try to get user from JWT authentication first
            user = self.scope.get("user")
            
            # If JWT authentication failed or not provided, fall back to URL parameter
            if not user.is_authenticated:
                self.user_id = self.scope['url_route']['kwargs']['user_id']
                user = await self.get_user(self.user_id)
                print(f"User fetched from URL: {user}")
            if user and user.is_authenticated:
                self.user_id = str(user.id)
                self.group_name = f"user_{self.user_id}"
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                await self.accept()
                print(f"✅ WebSocket connected: user_{self.user_id}")
            else:
                print("❌ Unauthorized WebSocket attempt")
                await self.close()
                
        except KeyError as e:
            print(f"❌ Missing required parameter: {e}")
            await self.close(code=4000)  # Custom close code for invalid parameters
        except ObjectDoesNotExist:
            print("❌ User not found")
            await self.close(code=4001)  # Custom close code for user not found
        except Exception as e:
            print(f"❌ Unexpected error during connection: {e}")
            await self.close(code=4002)  # Custom close code for other errors

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return None

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        print(f"WebSocket disconnected with code: {close_code}")

    async def receive_json(self, content):
        try:
            message_type = content.get('type')
            
            if message_type == 'ping':
                await self.send_json({'type': 'pong', 'timestamp': content.get('timestamp')})
            else:
                print(f"Received unknown message type: {message_type}")
                
        except Exception as e:
            print(f"Error processing message: {e}")

    @database_sync_to_async
    def get_driver_details(self, driver_id):
        driver = CustomUser.objects.filter(id=driver_id, role='driver').first()
        if not driver:
            return None
    
        vehicle_info = getattr(driver, 'vehicle_info', None)
    
        return {
            'driver_name': driver.username or f"Driver {driver.phone_number[-4:]}",
            'driver_phone': driver.phone_number,
            'vehicle_model': getattr(vehicle_info, 'car_model', 'Car'),
            'vehicle_number': getattr(vehicle_info, 'vehicle_number', 'NA'),
            'vehicle_type': getattr(vehicle_info, 'vehicle_type', 'Unknown'),
            'car_company': getattr(vehicle_info, 'car_company', ''),
            'year': getattr(vehicle_info, 'year', None),
        }
        
    async def ride_accepted(self, event):
        driver_details = await self.get_driver_details(event['driver_id'])
        if driver_details:
            await self.send_json({
                "type": "ride_accepted",
                "ride_id": event["ride_id"],
                "message": event["message"],
                "driver_id": event["driver_id"],
                **driver_details
            })
        else:
            await self.send_json({
                "type": "ride_accepted",
                "ride_id": event["ride_id"],
                "message": "Driver assigned but details unavailable",
                "driver_id": event["driver_id"],
                "driver_name": "Unknown Driver",
            })

    async def ride_cancelled(self, event):
        try:
            await self.send_json({
                "type": "ride_cancelled",
                "ride_id": event["ride_id"],
                "message": event["message"],
                "reason": event.get("reason", "No reason provided"),
                "driver_name": event.get("driver_name", "Unknown driver"),
                "driver_id": event.get("driver_id")
            })
        except Exception as e:
            print(f"Error sending ride_cancelled: {e}")

    async def ride_cancelled_by_user(self, event):
        try:
            await self.send_json({
                "type": "ride_cancelled_by_user",
                "ride_id": event["ride_id"],
                "message": event["message"],
                "user_name": event["user_name"],
                "user_id": event["user_id"],
                "timestamp": event.get("timestamp")
            })
        except Exception as e:
            print(f"Error sending ride_cancelled_by_user: {e}")

    
    async def driver_location_update(self, event):
        try:
            await self.send_json({
                "type": "driver_location",
                "ride_id": event["ride_id"],
                "latitude": event["latitude"],
                "longitude": event["longitude"],
                "timestamp": event["timestamp"]
            })
        except Exception as e:
            print(f"Error sending driver_location_update: {e}")

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
        self.ride_id = self.scope["url_route"]["kwargs"]["ride_id"]
        self.group_name = f"ride_{self.ride_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ride_completed(self, event):
        await self.send_json({
            "type": "ride_completed",
            "ride_id": event["ride_id"],
            "message": event["message"],
            "end_time": event["end_time"]
        })

    async def notify_otp_verified(self, event):
        await self.send_json({
            "type": "notify_otp_verified",  
            "ride_id": event["ride_id"],
            "message": event["message"]
        })



# ride sharing in emergency

class RideLocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f"ride_session_{self.session_id}"

        # Join group
        await self.channel_layer.group_add(
            self.group_name,
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