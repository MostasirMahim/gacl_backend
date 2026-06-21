# Run from project root:  DJANGO_ENV=development python3 e2e_test_outlet_ordering.py
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()

from decimal import Decimal
from django.db import transaction
from member.utils.factories import MemberFactory
from member.models import MembersFinancialBasics
from outlet.models import (
    Outlet, OutletItemCategory, OutletItem, CrossOrderingRule,
    OutletInventoryItem, OutletItemRecipe, OutletOrder,
)
from restaurant.models import (
    Restaurant, RestaurantCategory, RestaurantCuisineCategory,
    RestaurantItemCategory, RestaurantItem, RestaurantItemSetting, SpicyLevel,
)
from outlet.services.order_service import (
    create_outlet_order, verify_otp, advance_status, OutletOrderError)
from outlet.services.billing_service import bill_outlet_order

PASS, FAIL = [], []
def ok(m): PASS.append(m); print("PASS:", m)
def bad(m): FAIL.append(m); print("FAIL:", m)

try:
    with transaction.atomic():
        sid = transaction.savepoint()

        # fixtures: bar, cigar lounge, tea lounge, a restaurant
        bar = Outlet.objects.create(name="Sky Bar", outlet_type="bar")
        cigar = Outlet.objects.create(name="Cigar Room", outlet_type="cigar_lounge")
        tea = Outlet.objects.create(name="Tea Lounge", outlet_type="tea_lounge")

        cuisine = RestaurantCuisineCategory.objects.create(name="C")
        rcat = RestaurantCategory.objects.create(name="RC")
        rest = Restaurant.objects.create(name="Main Restaurant", cuisine_type=cuisine, restaurant_type=rcat)
        ricat = RestaurantItemCategory.objects.create(name="RIC")
        burger = RestaurantItem.objects.create(name="Burger", unit="plate",
            unit_cost=Decimal("100"), selling_price=Decimal("300"), category=ricat, restaurant=rest)
        RestaurantItemSetting.objects.create(item=burger, spicy_selectable=True)
        spicy = SpicyLevel.objects.create(name="Hot", rank=2)

        bcat = OutletItemCategory.objects.create(name="Drinks", outlet_type="bar")
        wine = OutletItem.objects.create(name="Wine", selling_price=Decimal("500"),
            category=bcat, outlet=bar)
        ccat = OutletItemCategory.objects.create(name="Cigars", outlet_type="cigar_lounge")
        cigar_item = OutletItem.objects.create(name="Premium Cigar", selling_price=Decimal("1500"),
            category=ccat, outlet=cigar)

        member = MemberFactory()
        MembersFinancialBasics.objects.create(member=member, dues_limit=Decimal("5000"))

        # cross-ordering rules per your brief:
        # bar -> cigar_lounge: allowed; cigar_lounge -> bar: denied
        # any outlet -> restaurant: allowed, requires room number
        CrossOrderingRule.objects.get_or_create(source_type="bar", target_type="cigar_lounge", defaults={"allowed":True})
        CrossOrderingRule.objects.get_or_create(source_type="cigar_lounge", target_type="bar", defaults={"allowed":False})
        CrossOrderingRule.objects.get_or_create(source_type="bar", target_type="restaurant", defaults={"allowed":True, "requires_room_number":True})
        CrossOrderingRule.objects.get_or_create(source_type="cigar_lounge", target_type="restaurant", defaults={"allowed":True, "requires_room_number":True})

        # 1. same-outlet order (bar buying wine)
        o1 = create_outlet_order(outlet=bar, member=member,
            items=[{"source":"bar","item_id":wine.id,"quantity":2}], require_otp=False)
        assert o1.sub_total == Decimal("1000"), o1.sub_total
        ok("Same-outlet order works (2 wine = 1000)")

        # 2. bar -> cigar allowed
        o2 = create_outlet_order(outlet=bar, member=member,
            items=[{"source":"cigar_lounge","item_id":cigar_item.id,"quantity":1}], require_otp=False)
        assert o2.sub_total == Decimal("1500"), o2.sub_total
        ok("Bar CAN order cigar-lounge items (allowed rule)")

        # 3. cigar -> bar DENIED
        try:
            create_outlet_order(outlet=cigar, member=member,
                items=[{"source":"bar","item_id":wine.id,"quantity":1}], require_otp=False)
            bad("Cigar->bar should be denied")
        except OutletOrderError:
            ok("Cigar lounge CANNOT order bar items (denied rule)")

        # 4. bar -> restaurant requires room number
        try:
            create_outlet_order(outlet=bar, member=member,
                items=[{"source":"restaurant","item_id":burger.id,"quantity":1}], require_otp=False)
            bad("Restaurant order without room should fail")
        except OutletOrderError:
            ok("Cross-order to restaurant without room number rejected")

        # 5. bar -> restaurant WITH room number works
        o5 = create_outlet_order(outlet=bar, member=member,
            items=[{"source":"restaurant","item_id":burger.id,"quantity":1,"spicy_level_id":spicy.id}],
            room_number="402", require_otp=False)
        assert o5.sub_total == Decimal("300"), o5.sub_total
        assert o5.items.first().restaurant_item_id == burger.id
        ok("Bar->restaurant WITH room number works (burger=300)")

        # 6. OTP flow
        o6 = create_outlet_order(outlet=bar, member=member,
            items=[{"source":"bar","item_id":wine.id,"quantity":1}], require_otp=True)
        assert o6.status == "pending_otp"
        try:
            verify_otp(order=o6, otp_code="000000"); bad("Wrong OTP accepted")
        except OutletOrderError: ok("Wrong OTP rejected (outlet)")
        verify_otp(order=o6, otp_code=o6.otp_code)
        o6.refresh_from_db(); assert o6.status == "confirmed"
        ok("OTP confirm works (outlet)")

        # 7. inventory deduction for outlet item
        grapes = OutletInventoryItem.objects.create(name="Grapes", unit="kg",
            current_quantity=Decimal("5"), outlet=bar)
        OutletItemRecipe.objects.create(item=wine, inventory_item=grapes, quantity_per_unit=Decimal("0.5"))
        advance_status(order=o6, target_status="preparing")
        grapes.refresh_from_db()
        assert grapes.current_quantity == Decimal("4.5"), grapes.current_quantity  # 5 - 0.5*1
        ok("Outlet inventory deducts via recipe (5 -> 4.5)")

        # 8. billing
        advance_status(order=o6, target_status="ready")
        advance_status(order=o6, target_status="served")
        inv = bill_outlet_order(order=o6, payment_mode="cash")
        o6.refresh_from_db()
        assert o6.status == "billed" and inv.status == "paid"
        ok("Outlet billing works (cash, paid)")

        transaction.savepoint_rollback(sid)
        print("\n[All test data rolled back - DB unchanged]")
except Exception as e:
    import traceback; traceback.print_exc(); bad(f"Unexpected: {e}")

print(f"\n===== RESULT: {len(PASS)} passed, {len(FAIL)} failed =====")
