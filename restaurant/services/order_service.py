"""
Restaurant order lifecycle service.

Encapsulates: order creation + OTP, OTP verification (-> kitchen),
kitchen transitions, inventory deduction, and billing into the existing
member_financial_management Invoice/Transaction/Payment/Sale chain.
"""
import logging
import uuid
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.utils import timezone

from restaurant.models import (
    RestaurantOrder, RestaurantOrderItem, RestaurantItem,
    RestaurantItemRecipe, RestaurantInventoryTransaction, SpicyLevel,
)
from core.utils.notifications import (
    generate_otp, send_order_otp, send_bill_notification,
)

logger = logging.getLogger("myapp")


class OrderError(Exception):
    """Domain error for order operations (maps to HTTP 400)."""


def _generate_order_number() -> str:
    return "ORD-" + uuid.uuid4().hex[:12].upper()


@transaction.atomic
def create_order(*, restaurant, member, items, serve_location="restaurant",
                 room_number="", guest=None, waiter=None, placed_by="member",
                 note="", require_otp=True):
    """
    items: list of dicts -> {"item_id", "quantity", "spicy_level_id"(opt), "note"(opt)}
    Returns the created RestaurantOrder (status pending_otp or confirmed).
    """
    if not items:
        raise OrderError("An order must contain at least one item.")
    if serve_location == "room" and not room_number:
        raise OrderError("room_number is required when serving to a room.")

    order = RestaurantOrder.objects.create(
        order_number=_generate_order_number(),
        status="pending_otp" if require_otp else "confirmed",
        serve_location=serve_location,
        room_number=room_number,
        placed_by=placed_by,
        restaurant=restaurant,
        member=member,
        guest=guest,
        waiter=waiter,
        note=note,
    )

    sub_total = Decimal("0.00")
    for line in items:
        item = RestaurantItem.objects.select_related("setting").get(
            id=line["item_id"], restaurant=restaurant)
        if not item.availability:
            raise OrderError(f"'{item.name}' is currently unavailable.")
        qty = int(line.get("quantity", 1))
        if qty < 1:
            raise OrderError("Quantity must be at least 1.")

        spicy = None
        spicy_id = line.get("spicy_level_id")
        if spicy_id:
            setting = getattr(item, "setting", None)
            if setting is None or not setting.spicy_selectable:
                raise OrderError(
                    f"Spicy level cannot be selected for '{item.name}'.")
            spicy = SpicyLevel.objects.get(id=spicy_id)

        unit_price = item.selling_price
        sub_total += unit_price * qty
        RestaurantOrderItem.objects.create(
            order=order, item=item, quantity=qty,
            unit_price=unit_price, spicy_level=spicy,
            note=line.get("note", ""),
        )

    order.sub_total = sub_total
    order.total_amount = sub_total  # taxes/discounts applied at billing
    if require_otp:
        otp = generate_otp()
        order.otp_code = otp
        order.otp_sent_at = timezone.now()
        phone = _resolve_phone(order)
        send_order_otp(phone, otp, order.order_number)
    else:
        order.confirmed_at = timezone.now()
    order.save()
    return order


def _resolve_phone(order) -> str:
    """Guest orders OTP the guest's phone; member orders the member's phone."""
    if order.guest is not None:
        return order.guest.phone
    contacts = order.member.contact_numbers.filter(is_active=True)
    primary = contacts.filter(is_primary=True).first() or contacts.first()
    return getattr(primary, "number", "") or "" if primary else ""


@transaction.atomic
def verify_otp(*, order, otp_code):
    if order.status != "pending_otp":
        raise OrderError("Order is not awaiting OTP confirmation.")
    if not order.otp_code or order.otp_code != str(otp_code).strip():
        raise OrderError("Invalid OTP code.")
    order.otp_verified = True
    order.status = "confirmed"
    order.confirmed_at = timezone.now()
    order.save(update_fields=["otp_verified", "status", "confirmed_at", "updated_at"])
    return order


# kitchen-driven status transitions
_KITCHEN_FLOW = {
    "confirmed": "preparing",
    "preparing": "ready",
    "ready": "served",
}


@transaction.atomic
def advance_kitchen_status(*, order, target_status):
    valid_targets = set(_KITCHEN_FLOW.values()) | {"cancelled"}
    if target_status not in valid_targets:
        raise OrderError(f"Invalid target status '{target_status}'.")
    if target_status == "cancelled":
        if order.status in ("billed", "served"):
            raise OrderError("Cannot cancel an order already served or billed.")
        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
        return order
    if _KITCHEN_FLOW.get(order.status) != target_status:
        raise OrderError(
            f"Cannot move from '{order.status}' to '{target_status}'.")
    # deduct inventory when cooking begins
    if target_status == "preparing":
        _deduct_inventory(order)
    order.status = target_status
    order.save(update_fields=["status", "updated_at"])
    return order


def _deduct_inventory(order):
    """Auto-deduct stock based on each item's recipe (if defined)."""
    for oi in order.items.select_related("item").all():
        recipe_lines = RestaurantItemRecipe.objects.filter(
            item=oi.item).select_related("inventory_item")
        for rl in recipe_lines:
            consumed = rl.quantity_per_unit * oi.quantity
            inv = rl.inventory_item
            inv.current_quantity = inv.current_quantity - consumed
            inv.save(update_fields=["current_quantity", "updated_at"])
            RestaurantInventoryTransaction.objects.create(
                inventory_item=inv, movement="out", quantity=consumed,
                reason=f"Consumed by order {order.order_number}", order=order,
            )
