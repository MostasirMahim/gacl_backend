"""
Outlet order lifecycle service (bar / tea lounge / cigar lounge).

Reuses the same lifecycle shape as restaurant ordering, but adds cross-outlet
ordering rules: a member sitting in one outlet may order items from another
source (another outlet type, or the restaurant) only if a CrossOrderingRule
allows it, honouring requires_room_number.
"""
import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from outlet.models import (
    Outlet, OutletItem, OutletOrder, OutletOrderItem, CrossOrderingRule,
    OutletItemRecipe, OutletInventoryTransaction,
)
from restaurant.models import RestaurantItem, SpicyLevel
from core.utils.notifications import generate_otp, send_order_otp

logger = logging.getLogger("myapp")


class OutletOrderError(Exception):
    """Domain error for outlet order operations (maps to HTTP 400)."""


def _generate_order_number() -> str:
    return "OUT-" + uuid.uuid4().hex[:12].upper()


def _check_cross_rule(source_type, target_type):
    """
    Returns (allowed: bool, requires_room: bool).
    Same-outlet ordering (source == target) is always allowed, no room needed.
    If no rule row exists for a cross combination, default DENY (safe).
    """
    if source_type == target_type:
        return True, False
    rule = CrossOrderingRule.objects.filter(
        source_type=source_type, target_type=target_type, is_active=True).first()
    if rule is None:
        return False, False
    return rule.allowed, rule.requires_room_number


@transaction.atomic
def create_outlet_order(*, outlet, member, items, guest=None, waiter=None,
                        placed_by="member", room_number="", note="",
                        require_otp=True):
    """
    items: list of dicts, each either
      {"source": "<this outlet type|other outlet type|restaurant>",
       "item_id": <id within that source>, "quantity", "spicy_level_id"(opt), "note"(opt)}
    """
    if not items:
        raise OutletOrderError("An order must contain at least one item.")

    order = OutletOrder.objects.create(
        order_number=_generate_order_number(),
        status="pending_otp" if require_otp else "confirmed",
        placed_by=placed_by, outlet=outlet, room_number=room_number,
        member=member, guest=guest, waiter=waiter, note=note,
    )

    sub_total = Decimal("0.00")
    needs_room = False
    for line in items:
        source = line.get("source")
        if not source or source == "outlet":
            source = outlet.outlet_type

        allowed, requires_room = _check_cross_rule(outlet.outlet_type, source)
        if not allowed:
            raise OutletOrderError(
                f"Ordering {source} items from a {outlet.outlet_type} is not allowed.")
        if requires_room:
            needs_room = True

        qty = int(line.get("quantity", 1))
        if qty < 1:
            raise OutletOrderError("Quantity must be at least 1.")

        outlet_item = None
        restaurant_item = None
        spicy = None

        if source == "restaurant":
            restaurant_item = RestaurantItem.objects.select_related("setting").get(
                id=line["item_id"])
            if not restaurant_item.availability:
                raise OutletOrderError(f"'{restaurant_item.name}' is unavailable.")
            unit_price = restaurant_item.selling_price
            spicy = _resolve_spicy_for_restaurant(restaurant_item, line.get("spicy_level_id"))
        else:
            # an outlet item (this outlet or another outlet of given type)
            outlet_item = OutletItem.objects.select_related("outlet").get(
                id=line["item_id"])
            if outlet_item.outlet.outlet_type != source:
                raise OutletOrderError("Item does not belong to the stated source.")
            if not outlet_item.availability:
                raise OutletOrderError(f"'{outlet_item.name}' is unavailable.")
            unit_price = outlet_item.selling_price
            spicy = _resolve_spicy_for_outlet(outlet_item, line.get("spicy_level_id"))

        sub_total += unit_price * qty
        OutletOrderItem.objects.create(
            order=order, outlet_item=outlet_item, restaurant_item=restaurant_item,
            quantity=qty, unit_price=unit_price, spicy_level=spicy,
            note=line.get("note", ""), source_type=source,
        )

    if needs_room and not room_number:
        raise OutletOrderError(
            "A room number is required when cross-ordering into this outlet.")

    order.sub_total = sub_total
    order.total_amount = sub_total
    if require_otp:
        otp = generate_otp()
        order.otp_code = otp
        order.otp_sent_at = timezone.now()
        send_order_otp(_resolve_phone(order), otp, order.order_number)
    else:
        order.confirmed_at = timezone.now()
    order.save()
    return order


def _resolve_spicy_for_outlet(outlet_item, spicy_id):
    if not spicy_id:
        return None
    if not outlet_item.spicy_selectable:
        raise OutletOrderError(
            f"Spicy level cannot be selected for '{outlet_item.name}'.")
    return SpicyLevel.objects.get(id=spicy_id)


def _resolve_spicy_for_restaurant(restaurant_item, spicy_id):
    if not spicy_id:
        return None
    setting = getattr(restaurant_item, "setting", None)
    if setting is None or not setting.spicy_selectable:
        raise OutletOrderError(
            f"Spicy level cannot be selected for '{restaurant_item.name}'.")
    return SpicyLevel.objects.get(id=spicy_id)


def _resolve_phone(order) -> str:
    if order.guest is not None:
        return order.guest.phone
    contacts = order.member.contact_numbers.filter(is_active=True)
    primary = contacts.filter(is_primary=True).first() or contacts.first()
    return getattr(primary, "number", "") or "" if primary else ""


@transaction.atomic
def verify_otp(*, order, otp_code):
    if order.status != "pending_otp":
        raise OutletOrderError("Order is not awaiting OTP confirmation.")
    if not order.otp_code or order.otp_code != str(otp_code).strip():
        raise OutletOrderError("Invalid OTP code.")
    order.otp_verified = True
    order.status = "confirmed"
    order.confirmed_at = timezone.now()
    order.save(update_fields=["otp_verified", "status", "confirmed_at", "updated_at"])
    return order


_KITCHEN_FLOW = {
    "confirmed": "preparing",
    "preparing": "ready",
    "ready": "served",
}


@transaction.atomic
def advance_status(*, order, target_status):
    valid_targets = set(_KITCHEN_FLOW.values()) | {"cancelled"}
    if target_status not in valid_targets:
        raise OutletOrderError(f"Invalid target status '{target_status}'.")
    if target_status == "cancelled":
        if order.status in ("billed", "served"):
            raise OutletOrderError("Cannot cancel an order already served or billed.")
        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
        return order
    if _KITCHEN_FLOW.get(order.status) != target_status:
        raise OutletOrderError(
            f"Cannot move from '{order.status}' to '{target_status}'.")
    if target_status == "preparing":
        _deduct_inventory(order)
    order.status = target_status
    order.save(update_fields=["status", "updated_at"])
    return order


def _deduct_inventory(order):
    """Deduct outlet inventory for outlet items that have recipes defined."""
    for oi in order.items.select_related("outlet_item").all():
        if not oi.outlet_item_id:
            continue  # restaurant-sourced lines deduct from restaurant inventory elsewhere
        recipe_lines = OutletItemRecipe.objects.filter(
            item=oi.outlet_item).select_related("inventory_item")
        for rl in recipe_lines:
            consumed = rl.quantity_per_unit * oi.quantity
            inv = rl.inventory_item
            inv.current_quantity = inv.current_quantity - consumed
            inv.save(update_fields=["current_quantity", "updated_at"])
            OutletInventoryTransaction.objects.create(
                inventory_item=inv, movement="out", quantity=consumed,
                reason=f"Consumed by order {order.order_number}", order=order,
            )
