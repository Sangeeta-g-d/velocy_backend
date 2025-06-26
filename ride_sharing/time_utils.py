from django.utils.timezone import is_aware, make_aware
from pytz import timezone
from datetime import datetime
from django.utils import timezone as dj_timezone

def convert_to_ist(dt):
    """
    Converts a datetime object to IST and returns a formatted string.
    """
    if not isinstance(dt, datetime):
        return None

    if not is_aware(dt):
        dt = make_aware(dt, dj_timezone.utc)

    ist = timezone('Asia/Kolkata')
    dt_ist = dt.astimezone(ist)

    return dt_ist.strftime('%Y-%m-%d %I:%M %p')  # Example: 2025-06-24 03:57 PM
