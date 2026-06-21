# Run from project root with:  DJANGO_ENV=development python3 e2e_test_restaurant_ordering.py
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()

from decimal import Decimal
from django.db import transaction
from django.test.utils import setup_test_environment

from member.utils.factories import MemberFactory
from restaurant.models import (
    Restaurant, RestaurantItem, RestaurantItemCategory, RestaurantItemSetting,
    RestaurantCuisineCategory, RestaurantCategory, SpicyLevel,
    RestaurantInventoryItem, RestaurantItemRecipe, RestaurantOrder,
)
from member.models import MembersFinancialBasics
from restaurant.services.order_service import create_order, verify_otp, advance_kitchen_status, OrderError
from restaurant.services.billing_service import bill_order

PASS, FAIL = [], []
def ok(m): PASS.append(m); print("PASS:", m)
def bad(m): FAIL.append(m); print("FAIL:", m)

try:
    with transaction.atomic():
        sid = transaction.savepoint()

        # --- fixtures ---
        cuisine = RestaurantCuisineCategory.objects.create(name="TestCuisine")
        rcat = RestaurantCategory.objects.create(name="TestRCat")
        rest = Restaurant.objects.create(
            name="E2E Test Restaurant", cuisine_type=cuisine, restaurant_type=rcat)
        icat = RestaurantItemCategory.objects.create(name="TestICat")
        item = RestaurantItem.objects.create(
            name="Test Burger", unit="plate", unit_cost=Decimal("100"),
            selling_price=Decimal("250"), category=icat, restaurant=rest)
        RestaurantItemSetting.objects.create(item=item, spicy_selectable=True, is_public_show=True)
        spicy = SpicyLevel.objects.create(name="Hot", rank=2)
        member = MemberFactory()
        # set a due limit
        MembersFinancialBasics.objects.create(member=member, dues_limit=Decimal("1000"))

        # inventory + recipe (1 burger consumes 0.2 kg beef)
        beef = RestaurantInventoryItem.objects.create(
            name="Beef", unit="kg", current_quantity=Decimal("10"),
            reorder_level=Decimal("2"), restaurant=rest)
        RestaurantItemRecipe.objects.create(item=item, inventory_item=beef, quantity_per_unit=Decimal("0.2"))

        # --- 1. create order with OTP ---
        order = create_order(restaurant=rest, member=member,
            items=[{"item_id": item.id, "quantity": 2, "spicy_level_id": spicy.id}],
            serve_location="room", room_number="305", require_otp=True)
        assert order.status == "pending_otp", order.status
        assert order.sub_total == Decimal("500"), order.sub_total
        assert order.otp_code, "OTP not generated"
        ok("Order created with OTP, totals correct (2x250=500)")

        # --- 2. spicy validation: disabled item rejects spicy ---
        item2 = RestaurantItem.objects.create(name="Plain Rice", unit="bowl",
            unit_cost=Decimal("20"), selling_price=Decimal("50"), category=icat, restaurant=rest)
        RestaurantItemSetting.objects.create(item=item2, spicy_selectable=False)
        try:
            create_order(restaurant=rest, member=member,
                items=[{"item_id": item2.id, "quantity": 1, "spicy_level_id": spicy.id}],
                require_otp=False)
            bad("Spicy level on non-spicy item should have been rejected")
        except OrderError:
            ok("Spicy level correctly rejected for spicy-disabled item")

        # --- 3. verify OTP ---
        try:
            verify_otp(order=order, otp_code="000000")
            bad("Wrong OTP accepted")
        except OrderError:
            ok("Wrong OTP rejected")
        verify_otp(order=order, otp_code=order.otp_code)
        order.refresh_from_db()
        assert order.status == "confirmed", order.status
        ok("Correct OTP confirms order -> status=confirmed")

        # --- 4. kitchen flow + inventory deduction ---
        advance_kitchen_status(order=order, target_status="preparing")
        beef.refresh_from_db(); order.refresh_from_db()
        assert order.status == "preparing", order.status
        assert beef.current_quantity == Decimal("9.6"), beef.current_quantity  # 10 - 0.2*2
        ok("Kitchen 'preparing' deducts inventory (10 -> 9.6 kg)")
        advance_kitchen_status(order=order, target_status="ready")
        advance_kitchen_status(order=order, target_status="served")
        order.refresh_from_db()
        assert order.status == "served", order.status
        ok("Kitchen flow preparing->ready->served works")

        # --- 5. invalid transition rejected ---
        try:
            advance_kitchen_status(order=order, target_status="preparing")
            bad("Invalid backward transition accepted")
        except OrderError:
            ok("Invalid status transition rejected")

        # --- 6. billing (cash, full settle) ---
        invoice = bill_order(order=order, payment_mode="cash")
        order.refresh_from_db()
        assert order.status == "billed", order.status
        assert invoice.total_amount == Decimal("500"), invoice.total_amount
        assert invoice.status == "paid", invoice.status
        assert invoice.balance_due == Decimal("0"), invoice.balance_due
        ok("Cash billing: invoice paid, total=500, balance=0, order=billed")

        # --- 7. due-limit enforcement ---
        order2 = create_order(restaurant=rest, member=member,
            items=[{"item_id": item.id, "quantity": 10}], require_otp=False)  # 2500
        advance_kitchen_status(order=order2, target_status="preparing")
        advance_kitchen_status(order=order2, target_status="ready")
        try:
            bill_order(order=order2, payment_mode="due")  # 2500 > 1000 limit
            bad("Due limit not enforced (2500 > 1000)")
        except OrderError:
            ok("Due limit enforced: 2500 on due rejected against 1000 limit")

        transaction.savepoint_rollback(sid)
        print("\n[All test data rolled back - DB unchanged]")
except Exception as e:
    import traceback; traceback.print_exc()
    bad(f"Unexpected exception: {e}")

print(f"\n===== RESULT: {len(PASS)} passed, {len(FAIL)} failed =====")
