# from pyfcm import FCMNotification
# from django.conf import settings
# from .models import FCMDevice

# push_service = FCMNotification(credentials_path=settings.FIREBASE_CREDENTIALS_PATH)

# def send_fcm_notification(user, title, body, data=None):
#     tokens = FCMDevice.objects.filter(user=user).values_list('token', flat=True)

#     if not tokens:
#         return

#     push_service.notify_multiple_devices(
#         registration_ids=list(tokens),
#         message_title=title,
#         message_body=body,
#         data_message=data or {},
#         sound="default"
#     )
