from firebase_admin import messaging
from velocy_backend.firebase_config import *   # ensures Firebase is initialized

def send_fcm_notification(user, title, body, data=None):
    from auth_api.models import FCMDevice  # avoid circular import

    devices = FCMDevice.objects.filter(user=user)

    for device in devices:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=device.token,
            data=data or {}
        )
        try:
            response = messaging.send(message)
            print(f"✅ Notification sent to {device.device_id}: {response}")
        except Exception as e:
            print(f"❌ Failed for {device.device_id}: {e}")
