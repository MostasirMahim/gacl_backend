"""
Centralised notification service (SMS / OTP).

This is a STUB with a clean interface. Wire a real provider (e.g. an SMS
gateway or SSLCommerz OTP) inside `_dispatch_sms` later -- the rest of the
codebase only calls the public helpers below and need not change.
"""
import logging
import random

logger = logging.getLogger("myapp")


def generate_otp(length: int = 6) -> str:
    start = 10 ** (length - 1)
    end = (10 ** length) - 1
    return str(random.randint(start, end))


def _dispatch_sms(phone: str, message: str) -> bool:
    """
    Real SMS sending goes here. For now we log and return True so the rest of
    the flow is testable without a live gateway.

    Replace the body with a provider call, e.g.:
        resp = requests.post(GATEWAY_URL, data={...}, timeout=10)
        return resp.ok
    """
    logger.info("SMS to %s: %s", phone, message)
    return True


def send_sms(phone: str, message: str) -> bool:
    if not phone:
        logger.warning("send_sms called with empty phone; skipped")
        return False
    try:
        return _dispatch_sms(phone, message)
    except Exception as exc:  # never let notification failure break a request
        logger.exception("send_sms failed: %s", exc)
        return False


def send_order_otp(phone: str, otp: str, order_number: str) -> bool:
    return send_sms(
        phone,
        f"Your order {order_number} confirmation code is {otp}.")


def send_bill_notification(phone: str, order_number: str, amount, paid: bool) -> bool:
    state = "PAID" if paid else "billed"
    return send_sms(
        phone,
        f"Order {order_number} {state}. Amount: BDT {amount}.")
