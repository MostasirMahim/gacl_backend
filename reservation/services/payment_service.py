"""
Reservation advance-payment service.

Pays the advance (gateway / pos / cash), creates the Invoice/Transaction/Payment/
Sale/Income records, marks the advance paid and confirms the slot.
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction

from member_financial_management.models import (
    Invoice, InvoiceType, Transaction, Payment, PaymentMethod,
    Sale, SaleType, Income, IncomeParticular, IncomeReceivingOption,
    IncomeReceivingType,
)
from member_financial_management.utils.functions import generate_unique_invoice_number
from core.utils.notifications import send_sms
from reservation.services.reservation_service import ReservationError

logger = logging.getLogger("myapp")

VALID_PAYMENT_MODES = {"pos", "sslcommerz", "cash"}


def _resolve_phone(member):
    contacts = member.contact_numbers.filter(is_active=True)
    primary = contacts.filter(is_primary=True).first() or contacts.first()
    return getattr(primary, "number", "") or "" if primary else ""


@transaction.atomic
def pay_advance(*, reservation, payment_mode, processed_by=None):
    if payment_mode not in VALID_PAYMENT_MODES:
        raise ReservationError(f"Unsupported payment mode '{payment_mode}'.")
    if reservation.advance_paid or reservation.status == "confirmed":
        raise ReservationError("Advance already paid / reservation confirmed.")
    if reservation.status != "pending_payment":
        raise ReservationError("Reservation is not awaiting payment.")

    amount = reservation.advance_amount or Decimal("0")
    member = reservation.member
    label = "Reservation - " + reservation.resource.get_resource_type_display().replace("_", " ").title()

    invoice_type, _ = InvoiceType.objects.get_or_create(name="Reservation")
    invoice = Invoice.objects.create(
        currency="BDT",
        invoice_number=generate_unique_invoice_number(),
        balance_due=Decimal("0"), paid_amount=amount,
        issue_date=date.today(), total_amount=amount,
        is_full_paid=True, status="paid",
        invoice_type=invoice_type, generated_by=processed_by, member=member,
    )

    payment_method, _ = PaymentMethod.objects.get_or_create(
        name={"pos": "POS", "sslcommerz": "SSLCommerz", "cash": "Cash"}[payment_mode])
    txn = Transaction.objects.create(
        amount=amount, member=member, invoice=invoice,
        payment_method=payment_method, transaction_type=payment_mode,
        status="paid", notes=f"{label} {reservation.reservation_number}",
    )
    Payment.objects.create(
        payment_amount=amount, payment_status="paid", payment_gateway=payment_mode,
        transaction=txn, invoice=invoice, member=member,
        payment_method=payment_method, processed_by=processed_by,
        notes=f"{label} {reservation.reservation_number}",
    )
    sale_type, _ = SaleType.objects.get_or_create(name="Reservation")
    sale = Sale.objects.create(
        sale_number=reservation.reservation_number, sub_total=amount,
        total_amount=amount, payment_status="paid",
        notes=f"{label} {reservation.reservation_number}",
        sale_source_type=sale_type, customer=member,
        payment_method=payment_method, invoice=invoice,
    )
    particular, _ = IncomeParticular.objects.get_or_create(name="Reservation Advance")
    received_from, _ = IncomeReceivingOption.objects.get_or_create(name="Member")
    receiving_type, _ = IncomeReceivingType.objects.get_or_create(name=payment_mode)
    Income.objects.create(
        receivable_amount=amount, final_receivable=amount,
        actual_received=amount, reaming_due=Decimal("0"),
        particular=particular, received_from_type=received_from,
        receiving_type=receiving_type, member=member,
        received_by=payment_method, sale=sale,
    )

    reservation.invoice = invoice
    reservation.advance_paid = True
    reservation.status = "confirmed"
    reservation.save(update_fields=["invoice", "advance_paid", "status", "updated_at"])

    send_sms(_resolve_phone(member),
             f"Reservation {reservation.reservation_number} confirmed. "
             f"Advance BDT {amount} received.")
    return invoice
