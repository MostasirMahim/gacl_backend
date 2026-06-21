"""
Outlet order billing service.

Mirrors restaurant billing: builds Invoice -> Transaction -> Payment -> Sale ->
Income from an outlet order, enforces the member due limit, sends bill SMS.
Invoice.restaurant is left null; the outlet is identified via the Sale/Income
particular and the order link.
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction

from member_financial_management.models import (
    Invoice, InvoiceItem, InvoiceType, Transaction, Payment, PaymentMethod,
    Sale, SaleType, Income, IncomeParticular, IncomeReceivingOption,
    IncomeReceivingType,
)
from member_financial_management.utils.functions import generate_unique_invoice_number
from member.models import MembersFinancialBasics
from core.utils.notifications import send_bill_notification
from outlet.services.order_service import OutletOrderError, _resolve_phone

logger = logging.getLogger("myapp")

VALID_PAYMENT_MODES = {"pos", "sslcommerz", "cash", "due"}


def _member_due_limit(member) -> Decimal:
    basics = MembersFinancialBasics.objects.filter(
        member=member, is_active=True).order_by("-id").first()
    return basics.dues_limit if basics else Decimal("0")


def _current_outstanding(member) -> Decimal:
    agg = Invoice.objects.filter(
        member=member, is_active=True,
        status__in=["unpaid", "partial_paid", "due"],
    ).values_list("balance_due", flat=True)
    return sum(agg, Decimal("0"))


@transaction.atomic
def bill_outlet_order(*, order, payment_mode, processed_by=None,
                      discount=Decimal("0"), tax=Decimal("0")):
    if payment_mode not in VALID_PAYMENT_MODES:
        raise OutletOrderError(f"Unsupported payment mode '{payment_mode}'.")
    if order.status == "billed" or order.invoice is not None:
        raise OutletOrderError("Order is already billed.")
    if order.status not in ("served", "ready"):
        raise OutletOrderError("Only a served/ready order can be billed.")

    member = order.member
    total_amount = (order.total_amount or Decimal("0")) - discount + tax
    if total_amount < 0:
        total_amount = Decimal("0")

    is_cash_settled = payment_mode in ("pos", "sslcommerz", "cash")
    paid_amount = total_amount if is_cash_settled else Decimal("0")
    balance_due = total_amount - paid_amount

    if balance_due > 0:
        projected = _current_outstanding(member) + balance_due
        if projected > _member_due_limit(member):
            raise OutletOrderError(
                "Member due limit exceeded; payment required to place this order on due.")

    type_label = order.outlet.get_outlet_type_display().title().replace("_", " ")
    invoice_type, _ = InvoiceType.objects.get_or_create(name=type_label)
    invoice = Invoice.objects.create(
        currency="BDT",
        invoice_number=generate_unique_invoice_number(),
        balance_due=balance_due, paid_amount=paid_amount,
        issue_date=date.today(), total_amount=total_amount,
        is_full_paid=balance_due == 0,
        discount=discount or None, tax=tax or None,
        status="paid" if balance_due == 0 else ("partial_paid" if paid_amount > 0 else "due"),
        invoice_type=invoice_type, generated_by=processed_by, member=member,
    )

    # link any restaurant items on the order to the invoice item (M2M is restaurant-only)
    invoice_item = InvoiceItem.objects.create(invoice=invoice)
    rest_item_ids = list(
        order.items.filter(restaurant_item__isnull=False)
        .values_list("restaurant_item_id", flat=True))
    if rest_item_ids:
        invoice_item.restaurant_items.set(rest_item_ids)

    payment_method, _ = PaymentMethod.objects.get_or_create(
        name={"pos": "POS", "sslcommerz": "SSLCommerz",
              "cash": "Cash", "due": "Due"}[payment_mode])

    txn = Transaction.objects.create(
        amount=paid_amount, member=member, invoice=invoice,
        payment_method=payment_method, transaction_type=payment_mode,
        status=invoice.status, notes=f"{type_label} order {order.order_number}",
    )
    Payment.objects.create(
        payment_amount=paid_amount, payment_status=invoice.status,
        payment_gateway=payment_mode, transaction=txn, invoice=invoice,
        member=member, payment_method=payment_method, processed_by=processed_by,
        notes=f"{type_label} order {order.order_number}",
    )

    sale_type, _ = SaleType.objects.get_or_create(name=type_label)
    sale = Sale.objects.create(
        sale_number=order.order_number, sub_total=order.sub_total,
        total_amount=total_amount, payment_status=invoice.status,
        notes=f"Order {order.order_number}", sale_source_type=sale_type,
        customer=member, payment_method=payment_method, invoice=invoice,
    )

    particular, _ = IncomeParticular.objects.get_or_create(name=f"{type_label} Sale")
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

    send_bill_notification(
        _resolve_phone(order), order.order_number, total_amount,
        paid=balance_due == 0)
    return invoice
