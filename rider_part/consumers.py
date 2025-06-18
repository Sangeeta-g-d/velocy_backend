# consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer

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


class RideNotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Comment out auth check for testing
        # self.user = self.scope["user"]
        # if self.user.is_authenticated:
        self.group_name = "ride_user_test"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # else:
        #     await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        # Optional: Handle client messages
        pass

    async def send_otp(self, event):
        await self.send_json({
            "type": "otp",
            "otp": event["otp"]
        })