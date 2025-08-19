# utils/otp.py

from twilio.rest import Client
import random
from django.conf import settings

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(phone_number, otp):
    from twilio.rest import Client
    from django.conf import settings

    print(f"Using TWILIO_PHONE_NUMBER: {settings.TWILIO_PHONE_NUMBER}")

    # ✨ Custom formatted message
    message_body = (
        f"Velocy Verse OTP: {otp}. "
        "Do not share this code with anyone. "
        "This code is valid for 2 minutes."
    )

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=message_body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=phone_number
    )
    return message.sid
