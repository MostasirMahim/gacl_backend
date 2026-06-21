"""
Vendor selection service.

select_offer(): mark one offer as the selected vendor for its category and
deactivate (reject) all competing offers in the same category — exactly the
behaviour requested: pick one, the rest get disabled.
"""
import logging
from decimal import Decimal

from django.db import transaction

from vendor.models import VendorServiceOffer, VendorPayment

logger = logging.getLogger("myapp")


class VendorError(Exception):
    """Domain error (maps to HTTP 400)."""


@transaction.atomic
def select_offer(*, offer):
    if offer.status == "rejected":
        raise VendorError("Cannot select a rejected offer; re-offer it first.")

    # reject every other offer in this category
    (VendorServiceOffer.objects
        .filter(category=offer.category, is_active=True)
        .exclude(id=offer.id)
        .update(status="rejected", is_active=False))

    offer.status = "selected"
    offer.is_active = True
    offer.save(update_fields=["status", "is_active", "updated_at"])
    return offer


@transaction.atomic
def record_vendor_payment(*, offer, amount, note="", created_by=None):
    if offer.status != "selected":
        raise VendorError("Only the selected vendor for a category can be paid.")
    payment = VendorPayment.objects.create(
        offer=offer, amount=amount, note=note, created_by=created_by)

    # record into central expense ledger
    try:
        from finance_core.services.ledger_service import record_expense
        record_expense(
            source_module="vendor",
            category_name="Vendor Services",
            amount=amount,
            description=f"{offer.vendor.name} - {offer.category.name}",
            reference_type="vendor_payment", reference_id=payment.id,
            created_by=created_by,
        )
    except Exception as exc:
        logger.warning("Could not record vendor expense: %s", exc)
    return payment
