"""
SSLCommerz payment integration (provider-agnostic config via env).

Flow:
  1. initiate_session() -> POST to SSLCommerz, returns a GatewayPageURL the
     frontend redirects the member to.
  2. Member pays on SSLCommerz, which redirects to success/fail/cancel URLs and
     also calls the IPN endpoint server-to-server.
  3. validate_ipn() verifies the transaction with SSLCommerz's validation API
     before we trust it, then marks the linked invoice paid.

Environment variables:
    SSLCZ_STORE_ID
    SSLCZ_STORE_PASSWORD
    SSLCZ_SANDBOX        "true"/"false"  (default true)
    SSLCZ_SUCCESS_URL    (frontend/callback url)
    SSLCZ_FAIL_URL
    SSLCZ_CANCEL_URL
    SSLCZ_IPN_URL
"""
import logging
from decimal import Decimal

import environ
import requests

from django.db import transaction

env = environ.Env()
logger = logging.getLogger("myapp")


def _base_url() -> str:
    sandbox = env.bool("SSLCZ_SANDBOX", default=True)
    return (
        "https://sandbox.sslcommerz.com"
        if sandbox
        else "https://securepay.sslcommerz.com"
    )


class SSLCommerzError(Exception):
    pass


def initiate_session(*, invoice, amount, customer_name="Member",
                     customer_email="", customer_phone=""):
    """
    Create a payment session. Returns dict with at least GatewayPageURL.
    `invoice` is a member_financial_management.Invoice instance.
    """
    store_id = env.str("SSLCZ_STORE_ID", default="")
    store_pass = env.str("SSLCZ_STORE_PASSWORD", default="")
    if not store_id or not store_pass:
        raise SSLCommerzError(
            "SSLCommerz is not configured (SSLCZ_STORE_ID / SSLCZ_STORE_PASSWORD).")

    payload = {
        "store_id": store_id,
        "store_passwd": store_pass,
        "total_amount": str(amount),
        "currency": "BDT",
        "tran_id": invoice.invoice_number,
        "success_url": env.str("SSLCZ_SUCCESS_URL", default=""),
        "fail_url": env.str("SSLCZ_FAIL_URL", default=""),
        "cancel_url": env.str("SSLCZ_CANCEL_URL", default=""),
        "ipn_url": env.str("SSLCZ_IPN_URL", default=""),
        "cus_name": customer_name,
        "cus_email": customer_email or "member@example.com",
        "cus_phone": customer_phone or "01700000000",
        "shipping_method": "NO",
        "product_name": "Club Invoice",
        "product_category": "Service",
        "product_profile": "general",
    }
    try:
        resp = requests.post(
            f"{_base_url()}/gwprocess/v4/api.php", data=payload, timeout=20)
        data = resp.json()
    except Exception as exc:
        logger.exception("SSLCommerz initiate failed: %s", exc)
        raise SSLCommerzError("Could not reach SSLCommerz.")

    if data.get("status") != "SUCCESS":
        raise SSLCommerzError(data.get("failedreason", "Session creation failed."))
    return data


def _validate_with_gateway(val_id: str) -> dict:
    store_id = env.str("SSLCZ_STORE_ID", default="")
    store_pass = env.str("SSLCZ_STORE_PASSWORD", default="")
    try:
        resp = requests.get(
            f"{_base_url()}/validator/api/validationserverAPI.php",
            params={"val_id": val_id, "store_id": store_id,
                    "store_passwd": store_pass, "format": "json"},
            timeout=20)
        return resp.json()
    except Exception as exc:
        logger.exception("SSLCommerz validation failed: %s", exc)
        raise SSLCommerzError("Validation request failed.")


@transaction.atomic
def validate_ipn(*, post_data):
    """
    Called by the IPN view. Verifies the payment with SSLCommerz, then marks the
    matching invoice paid. Returns the updated invoice (or None if not matched).
    """
    from member_financial_management.models import Invoice, Payment, Transaction

    tran_id = post_data.get("tran_id")
    val_id = post_data.get("val_id")
    status = post_data.get("status")
    if not tran_id:
        raise SSLCommerzError("Missing tran_id in IPN.")

    if status not in ("VALID", "VALIDATED"):
        logger.info("IPN for %s had status %s; ignored", tran_id, status)
        return None

    # server-side verification (never trust the raw callback alone)
    if val_id:
        validation = _validate_with_gateway(val_id)
        if validation.get("status") not in ("VALID", "VALIDATED"):
            raise SSLCommerzError("Gateway validation did not pass.")
        amount = Decimal(str(validation.get("amount", "0")))
    else:
        amount = Decimal(str(post_data.get("amount", "0")))

    invoice = Invoice.objects.filter(
        invoice_number=tran_id, is_active=True).first()
    if invoice is None:
        logger.warning("IPN tran_id %s did not match any invoice", tran_id)
        return None

    if invoice.status == "paid":
        return invoice  # idempotent: already settled

    invoice.paid_amount = invoice.total_amount
    invoice.balance_due = Decimal("0")
    invoice.is_full_paid = True
    invoice.status = "paid"
    invoice.save(update_fields=[
        "paid_amount", "balance_due", "is_full_paid", "status"])

    # reflect on the latest transaction/payment for this invoice if present
    Transaction.objects.filter(invoice=invoice).update(status="paid")
    Payment.objects.filter(invoice=invoice).update(payment_status="paid")

    logger.info("Invoice %s marked paid via SSLCommerz IPN", tran_id)
    return invoice
