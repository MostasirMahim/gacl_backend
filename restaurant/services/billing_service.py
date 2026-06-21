"""
Restaurant order billing service.

Converts a served order into the existing financial chain:
Invoice -> Transaction -> Payment -> Sale -> Income, enforcing the member's
due limit and sending an immutable bill SMS. Payment modes: pos, sslcommerz, cash.
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.utils import timezone

from member_financial_management.models import (
    Invoice, InvoiceItem, InvoiceType, Transaction, Payment, PaymentMethod,
    Sale, SaleType, Income, IncomeParticular, IncomeReceivingOption,
    IncomeReceivingType,
)
from member_financial_management.utils.functions import generate_unique_invoice_number
from member.models import MembersFinancialBasics
from core.utils.notifications import send_bill_notification
from restaurant.services.order_service import OrderError, _resolve_phone

logger = logging.getLogger("myapp")

VALID_PAYMENT_MODES = {"pos", "sslcommerz", "cash", "due"}


def _member_due_limit(member) -> Decimal:
    basics = MembersFinancialBasics.objects.filter(
        member=member, is_active=True).order_by("-id").first()
    return basics.dues_limit if basics else Decimal("0")


def _current_outstanding(member) -> Decimal:
    """Sum of balance_due on the member's unpaid/partial invoices."""
    agg = Invoice.objects.filter(
        member=member, is_active=True,
        status__in=["unpaid", "partial_paid", "due"],
    ).values_list("balance_due", flat=True)
    return sum(agg, Decimal("0"))


@transaction.atomic
def bill_order(*, order, payment_mode, processed_by=None, discount=Decimal("0"),
               tax=Decimal("0")):
    """
    Generates the invoice for an order and records payment per mode.
    'due' / partial leaves a balance (subject to the member's due limit).
    Returns the created Invoice.
    """
    if payment_mode not in VALID_PAYMENT_MODES:
        raise OrderError(f"Unsupported payment mode '{payment_mode}'.")
    if order.status == "billed" or order.invoice is not None:
        raise OrderError("Order is already billed.")
    if order.status not in ("served", "ready"):
        raise OrderError("Only a served/ready order can be billed.")

    member = order.member
    total_amount = (order.total_amount or Decimal("0")) - discount + tax
    if total_amount < 0:
        total_amount = Decimal("0")

    is_cash_settled = payment_mode in ("pos", "sslcommerz", "cash")
    paid_amount = total_amount if is_cash_settled else Decimal("0")
    balance_due = total_amount - paid_amount

    # Enforce due limit when the bill leaves a balance
    if balance_due > 0:
        projected = _current_outstanding(member) + balance_due
        limit = _member_due_limit(member)
        if projected > limit:
            raise OrderError(
                "Member due limit exceeded; payment required to place this order on due.")

    invoice_type, _ = InvoiceType.objects.get_or_create(name="Restaurant")
    invoice = Invoice.objects.create(
        currency="BDT",
        invoice_number=generate_unique_invoice_number(),
        balance_due=balance_due,
        paid_amount=paid_amount,
        issue_date=date.today(),
        total_amount=total_amount,
        is_full_paid=balance_due == 0,
        discount=discount or None,
        tax=tax or None,
        status="paid" if balance_due == 0 else ("partial_paid" if paid_amount > 0 else "due"),
        invoice_type=invoice_type,
        generated_by=processed_by,
        member=member,
        restaurant=order.restaurant,
    )

    invoice_item = InvoiceItem.objects.create(invoice=invoice)
    invoice_item.restaurant_items.set(
        list(order.items.values_list("item_id", flat=True)))

    payment_method, _ = PaymentMethod.objects.get_or_create(
        name={"pos": "POS", "sslcommerz": "SSLCommerz",
              "cash": "Cash", "due": "Due"}[payment_mode])

    txn = Transaction.objects.create(
        amount=paid_amount, member=member, invoice=invoice,
        payment_method=payment_method,
        transaction_type=payment_mode,
        status=invoice.status,
        notes=f"Restaurant order {order.order_number}",
    )
    Payment.objects.create(
        payment_amount=paid_amount, payment_status=invoice.status,
        payment_gateway=payment_mode, transaction=txn, invoice=invoice,
        member=member, payment_method=payment_method, processed_by=processed_by,
        notes=f"Restaurant order {order.order_number}",
    )

    sale_type, _ = SaleType.objects.get_or_create(name="Restaurant")
    sale = Sale.objects.create(
        sale_number=order.order_number,
        sub_total=order.sub_total, total_amount=total_amount,
        payment_status=invoice.status, notes=f"Order {order.order_number}",
        sale_source_type=sale_type, customer=member,
        payment_method=payment_method, invoice=invoice,
    )

    particular, _ = IncomeParticular.objects.get_or_create(name="Restaurant Sale")
    received_from, _ = IncomeReceivingOption.objects.get_or_create(name="Member")
    receiving_type, _ = IncomeReceivingType.objects.get_or_create(name=payment_mode)
    Income.objects.create(
        receivable_amount=total_amount, final_receivable=total_amount,
        actual_received=paid_amount, reaming_due=balance_due,
        particular=particular, received_from_type=received_from,
        receiving_type=receiving_type, member=member,
        received_by=payment_method, sale=sale,
    )

    order.invoice = invoice
    order.status = "billed"
    order.save(update_fields=["invoice", "status", "updated_at"])

    # immutable bill SMS (amount comes from server-side invoice, not client)
    send_bill_notification(
        _resolve_phone(order), order.order_number, total_amount,
        paid=balance_due == 0)

    return invoice
