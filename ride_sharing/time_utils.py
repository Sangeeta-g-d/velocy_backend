from django.utils.timezone import is_aware
from pytz import timezone
from datetime import datetime

def convert_to_ist(dt):
    """
    Converts a datetime object to IST (Asia/Kolkata).
    """
    if not isinstance(dt, datetime):
        return None  # or raise TypeError

    if not is_aware(dt):
        from django.utils.timezone import make_aware
        from django.utils import timezone as dj_timezone
        dt = make_aware(dt, dj_timezone.utc)

    ist = timezone('Asia/Kolkata')
    return dt.astimezone(ist)
