from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import F
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from admin_part.models import PlatformSetting
from rider_part.models import DriverPendingFee

def get_platform_fee_for_amount(amount: Decimal) -> Decimal:
    setting = PlatformSetting.objects.filter(fee_reason="platform fees", is_active=True).first()
    if not setting:
        return Decimal("0.00")
    if setting.fee_type == "percentage":
        fee = (amount * setting.fee_value / Decimal("100")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
    else:
        fee = Decimal(setting.fee_value).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
    return fee

def notify_user(user_id: int, event_type: str, payload: dict):
    """Send websocket group event to user group 'user_{user_id}'."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "type": "notification.message",
            "event": event_type,
            "data": payload,
        },
    )

def settle_pending_fees(driver, incoming_amount: Decimal) -> Decimal:
    """
    Lock driver's pending fees, settle them in FIFO order, and return remaining amount
    after fully/partially settling pending fees.
    """
    remaining = incoming_amount
    # Lock the pending fee rows for this driver to avoid races
    with transaction.atomic():
        pending_qs = DriverPendingFee.objects.select_for_update().filter(driver=driver, settled=False).order_by("created_at")
        for fee in pending_qs:
            if remaining <= Decimal("0.00"):
                break
            if remaining >= fee.amount:
                remaining -= fee.amount
                fee.settled = True
                fee.save(update_fields=["settled"])
            else:
                # partially settle: reduce fee.amount by remaining and zero out remaining
                fee.amount = (fee.amount - remaining).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
                fee.save(update_fields=["amount"])
                remaining = Decimal("0.00")
    return remaining.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
