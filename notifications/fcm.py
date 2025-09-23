from firebase_admin import messaging
from velocy_backend.firebase_config import *   # ensures Firebase is initialized

def send_fcm_notification(user, title, body, data=None):
    from auth_api.models import UserFCMToken  # avoid circular import

    tokens = UserFCMToken.objects.filter(user=user)
    print(f"[DEBUG] Found {tokens.count()} FCM tokens for user {user.id}")

    for token_obj in tokens:
        print(f"[DEBUG] Preparing notification for {user.phone_number} ({token_obj.device_type})")

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=token_obj.token,
            data=data or {}
        )
        try:
            response = messaging.send(message)
            print(f"✅ Notification sent to {user.phone_number} | token={token_obj.token[:15]}... | response={response}")
        except Exception as e:
            import traceback
            print(f"❌ Failed for {user.phone_number} | token={token_obj.token[:15]}... | error={e}")
            print(traceback.format_exc())
