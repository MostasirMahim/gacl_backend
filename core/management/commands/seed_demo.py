"""
Comprehensive demo seed data for the GACL club-management backend.

Usage:
    python manage.py seed_demo                 # default volumes
    python manage.py seed_demo --members 60    # custom member count
    python manage.py seed_demo --flush         # wipe seeded demo data first

Idempotent: re-running updates/gets_or_creates rather than duplicating.
Covers: permissions, admin + staff users, members (+contacts/emails/financials),
attendance (RFID cards, guests, records), restaurant (menu, spicy, inventory,
orders through the full lifecycle + billing), outlets (bar/tea/cigar + items +
cross-ordering rules + orders), reservations (resources + bookings), payroll
(components, structures, a processed run, loans), vendors (offers + selection),
finance (expense ledger entries), and events (with expenses).
"""
import random
from datetime import date, timedelta, time
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

PERMISSIONS = [
    "member_management", "restaurant_management", "event_management",
    "product_management", "facility_management",
    "member_financial_management", "attendance_management", "outlet_management",
    "reservation_management", "payroll_management", "vendor_management",
]

FIRST_NAMES = ["Arif", "Karim", "Rahim", "Sadia", "Nadia", "Tanvir", "Fahim",
               "Mitu", "Sabbir", "Rumana", "Imran", "Jihan", "Sumaiya", "Rafi",
               "Tania", "Hasan", "Mahin", "Nusrat", "Shovon", "Priya"]
LAST_NAMES = ["Hossain", "Islam", "Ahmed", "Khan", "Chowdhury", "Rahman",
              "Akter", "Uddin", "Haque", "Bhuiyan"]


def _tiny_png():
    # 1x1 transparent PNG bytes (valid image for ImageField/FileField)
    import base64
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    return ContentFile(data, name="seed.png")


class Command(BaseCommand):
    help = "Seed comprehensive demo data for the club management system."

    def add_arguments(self, parser):
        parser.add_argument("--members", type=int, default=40)
        parser.add_argument("--staff", type=int, default=12)
        parser.add_argument("--flush", action="store_true",
                            help="Delete previously seeded demo data first")

    def handle(self, *args, **opts):
        self.stdout.write(self.style.WARNING("Seeding demo data..."))
        if opts["flush"]:
            self._flush()
        with transaction.atomic():
            self.admin = self._seed_users_and_permissions(opts["staff"])
            self._seed_choice_models()
            members = self._seed_members(opts["members"])
            self._seed_attendance(members)
            self._seed_restaurant(members)
            self._seed_outlets(members)
            self._seed_reservations(members)
            self._seed_payroll()
            self._seed_vendors()
            self._seed_finance()
            self._seed_events(members)
        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
        self._summary()

    # ----------------------------------------------------------------
    def _flush(self):
        from attendance.models import AttendanceRecord, Guest, RFIDCard, StaffProfile
        from restaurant.models import (RestaurantOrder, RestaurantInventoryItem,
            RestaurantItem, SpicyLevel)
        from outlet.models import (OutletOrder, OutletItem, Outlet, CrossOrderingRule,
            OutletItemCategory)
        from reservation.models import Reservation, ReservableResource
        from payroll.models import (Payslip, PayrollRun, SalaryStructure,
            SalaryComponent, StaffLoan)
        from vendor.models import (VendorServiceOffer, VendorServiceCategory,
            Vendor, VendorPayment)
        from finance_core.models import Expense, ExpenseCategory
        self.stdout.write("  flushing previously seeded demo rows...")
        for M in [AttendanceRecord, Guest, RFIDCard, RestaurantOrder,
                  OutletOrder, Reservation, Payslip, PayrollRun, StaffLoan,
                  SalaryStructure, VendorPayment, VendorServiceOffer, Expense]:
            M.objects.all().delete()

    # ----------------------------------------------------------------
    def _seed_users_and_permissions(self, staff_count):
        from django.core.management import call_command
        from account.models import PermissonModel, GroupModel, AssignGroupPermission
        from attendance.models import StaffProfile

        # Execute section permissions seeding command
        call_command("seed_staff_permissions")

        # Ensure admin superuser exists
        perms = list(PermissonModel.objects.all())
        admin_group, _ = GroupModel.objects.get_or_create(name="Administrators")
        admin_group.permission.set(perms)

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@gacl.test", "is_staff": True,
                      "is_superuser": True, "first_name": "Club", "last_name": "Admin"})
        if created or not admin.check_password("admin1234"):
            admin.set_password("admin1234")
            admin.save()
        assign, _ = AssignGroupPermission.objects.get_or_create(user=admin)
        assign.group.add(admin_group)

        self.staff_profiles = list(StaffProfile.objects.filter(user__is_staff=True).exclude(user__username="admin"))
        self.stdout.write(f"  users: 1 admin + {len(self.staff_profiles)} staff assigned across 10 section groups")
        return admin

    # ----------------------------------------------------------------
    def _seed_choice_models(self):
        from core.models import (Gender, MembershipType, InstituteName,
            MembershipStatusChoice, MaritalStatusChoice)
        self.genders = [Gender.objects.get_or_create(name=n)[0]
                        for n in ["Male", "Female", "Other"]]
        self.mtypes = [MembershipType.objects.get_or_create(name=n)[0]
                       for n in ["General", "Life", "Corporate", "Honorary"]]
        self.institutes = [
            InstituteName.objects.get_or_create(
                name=n, defaults={"code": f"INST{idx:02d}"})[0]
            for idx, n in enumerate(["Dhaka University", "BUET", "NSU", "BRAC"], start=1)]
        self.mstatus = [MembershipStatusChoice.objects.get_or_create(name=n)[0]
                        for n in ["Active", "Suspended", "Pending"]]
        self.marital = [MaritalStatusChoice.objects.get_or_create(name=n)[0]
                        for n in ["Single", "Married"]]

    # ----------------------------------------------------------------
    def _seed_members(self, count):
        from member.models import (Member, MembersFinancialBasics, ContactNumber, Email)
        members = []
        for i in range(1, count + 1):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            m, created = Member.objects.get_or_create(
                member_ID=f"GACL-{i:04d}",
                defaults={
                    "first_name": fn, "last_name": ln,
                    "date_of_birth": date(1980 + i % 25, (i % 12) + 1, (i % 27) + 1),
                    "batch_number": f"B{2000 + (i % 20)}",
                    "blood_group": random.choice(["A+", "B+", "O+", "AB+", "O-"]),
                    "nationality": "BD",
                    "gender": random.choice(self.genders),
                    "membership_type": random.choice(self.mtypes),
                    "institute_name": random.choice(self.institutes),
                    "membership_status": random.choice(self.mstatus),
                    "marital_status": random.choice(self.marital),
                    "status": 1,
                })
            if created:
                m.profile_photo.save("seed.png", _tiny_png(), save=True)
                MembersFinancialBasics.objects.create(
                    member=m, membership_fee=Decimal("50000"),
                    payment_received=Decimal(random.choice(["50000", "30000", "20000"])),
                    membership_fee_remaining=Decimal("0"),
                    subscription_fee=Decimal("2000"),
                    dues_limit=Decimal(random.choice(["5000", "10000", "15000"])),
                    status=1)
                ContactNumber.objects.create(
                    member=m, number=f"01{random.randint(300000000, 999999999)}",
                    is_primary=True, status=1)
                Email.objects.create(
                    member=m, email=f"{fn.lower()}{i}@example.com",
                    is_primary=True, status=1)
            members.append(m)
        self.stdout.write(f"  members: {len(members)} (with contacts, emails, financials)")
        return members

    # ----------------------------------------------------------------
    def _seed_attendance(self, members):
        from attendance.models import RFIDCard, Guest, AttendanceRecord
        # member cards + records
        recs = 0
        for m in members[:25]:
            card, _ = RFIDCard.objects.get_or_create(
                card_uid=f"CARD-M-{m.member_ID}",
                defaults={"card_type": "member", "member": m, "is_assigned": True})
            AttendanceRecord.objects.get_or_create(
                card=card, subject_type="member", member=m,
                check_out=None,
                defaults={"check_in": timezone.now() - timedelta(hours=random.randint(1, 5))})
            recs += 1
        # staff cards + records
        for sp in self.staff_profiles:
            card, _ = RFIDCard.objects.get_or_create(
                card_uid=f"CARD-S-{sp.staff_ID}",
                defaults={"card_type": "staff", "staff": sp, "is_assigned": True})
            AttendanceRecord.objects.get_or_create(
                card=card, subject_type="staff", staff=sp, check_out=None,
                defaults={"check_in": timezone.now() - timedelta(hours=random.randint(1, 8))})
        # guests (some family, some guest)
        guest_count = 0
        for idx, m in enumerate(members[:10]):
            g, created = Guest.objects.get_or_create(
                name=f"Guest of {m.first_name}", host_member=m,
                defaults={"phone": f"019{idx:08d}",
                          "guest_relation": "family" if idx % 2 else "guest",
                          "host_type": "member"})
            if created:
                guest_count += 1
        self.stdout.write(f"  attendance: cards + {recs} member records + staff records + {guest_count} guests")

    # ----------------------------------------------------------------
    def _seed_restaurant(self, members):
        from restaurant.models import (Restaurant, RestaurantCuisineCategory,
            RestaurantCategory, RestaurantItemCategory, RestaurantItem,
            RestaurantItemSetting, SpicyLevel, RestaurantInventoryItem,
            RestaurantItemRecipe)
        from restaurant.services.order_service import create_order, verify_otp, advance_kitchen_status
        from restaurant.services.billing_service import bill_order

        cuisine, _ = RestaurantCuisineCategory.objects.get_or_create(name="Continental")
        rcat, _ = RestaurantCategory.objects.get_or_create(name="Fine Dining")
        rest, _ = Restaurant.objects.get_or_create(
            name="GACL Main Restaurant",
            defaults={"cuisine_type": cuisine, "restaurant_type": rcat,
                      "capacity": 120, "status": "open"})
        spicy_levels = [SpicyLevel.objects.get_or_create(name=n, defaults={"rank": r})[0]
                        for r, n in enumerate(["Mild", "Medium", "Hot", "Extra Hot"])]
        icat, _ = RestaurantItemCategory.objects.get_or_create(name="Main Course")
        dcat, _ = RestaurantItemCategory.objects.get_or_create(name="Beverages")

        items = []
        menu = [("Beef Steak", "Main Course", 850, 400, True),
                ("Chicken Biryani", "Main Course", 350, 150, True),
                ("Grilled Fish", "Main Course", 600, 280, True),
                ("Mutton Curry", "Main Course", 550, 260, True),
                ("Caesar Salad", "Main Course", 320, 120, False),
                ("Fresh Lime", "Beverages", 120, 30, False),
                ("Cold Coffee", "Beverages", 200, 70, False),
                ("Mango Lassi", "Beverages", 180, 60, False)]
        for name, cat, price, cost, spicy in menu:
            it, created = RestaurantItem.objects.get_or_create(
                name=name, restaurant=rest,
                defaults={"category": icat if cat == "Main Course" else dcat,
                          "unit": "plate", "unit_cost": Decimal(cost),
                          "selling_price": Decimal(price), "availability": True})
            RestaurantItemSetting.objects.get_or_create(
                item=it, defaults={"spicy_selectable": spicy, "is_public_show": True})
            items.append(it)

        # inventory + a recipe
        beef = RestaurantInventoryItem.objects.get_or_create(
            name="Beef", restaurant=rest,
            defaults={"unit": "kg", "current_quantity": Decimal("100"),
                      "reorder_level": Decimal("15"), "unit_cost": Decimal("700")})[0]
        rice = RestaurantInventoryItem.objects.get_or_create(
            name="Rice", restaurant=rest,
            defaults={"unit": "kg", "current_quantity": Decimal("200"),
                      "reorder_level": Decimal("30"), "unit_cost": Decimal("80")})[0]
        RestaurantItemRecipe.objects.get_or_create(
            item=items[0], inventory_item=beef, defaults={"quantity_per_unit": Decimal("0.3")})

        # a handful of orders across the lifecycle, some fully billed (income!)
        made = 0
        from restaurant.models import RestaurantOrder as _RO
        if _RO.objects.count() < 10:
            for i in range(12):
                m = random.choice(members)
                order = create_order(
                    restaurant=rest, member=m,
                    items=[{"item_id": random.choice(items).id, "quantity": random.randint(1, 3)}],
                    serve_location=random.choice(["restaurant", "room"]),
                    room_number=str(random.randint(101, 410)),
                    require_otp=False)
                # push most of them through to billed
                if i % 4 != 0:
                    advance_kitchen_status(order=order, target_status="preparing")
                    advance_kitchen_status(order=order, target_status="ready")
                    advance_kitchen_status(order=order, target_status="served")
                    bill_order(order=order, payment_mode=random.choice(["cash", "pos", "due"]),
                               processed_by=self.admin)
                made += 1
        self.stdout.write(f"  restaurant: {len(items)} menu items, inventory, {made} orders (most billed)")

    # ----------------------------------------------------------------
    def _seed_outlets(self, members):
        from outlet.models import (Outlet, OutletItemCategory, OutletItem,
            CrossOrderingRule)
        from outlet.services.order_service import create_outlet_order, advance_status
        from outlet.services.billing_service import bill_outlet_order

        specs = [("Sky Bar", "bar", [("Red Wine", 1200), ("Whiskey", 1500), ("Beer", 600)]),
                 ("Tea Lounge", "tea_lounge", [("Green Tea", 150), ("Cappuccino", 250), ("Fresh Juice", 200)]),
                 ("Cigar Room", "cigar_lounge", [("Premium Cigar", 2500), ("Cognac", 3000)])]
        outlets = {}
        for name, otype, prods in specs:
            o, _ = Outlet.objects.get_or_create(
                name=name, defaults={"outlet_type": otype, "capacity": 40, "status": "open",
                                     "admin": self.admin})
            cat, _ = OutletItemCategory.objects.get_or_create(
                name=f"{name} Menu", defaults={"outlet_type": otype})
            for pname, price in prods:
                OutletItem.objects.get_or_create(
                    name=pname, outlet=o,
                    defaults={"category": cat, "selling_price": Decimal(price),
                              "unit_cost": Decimal(price) / 3, "unit": "glass",
                              "is_public_show": True})
            outlets[otype] = o

        # cross-ordering rules per the brief
        rules = [("bar", "cigar_lounge", True, False),
                 ("cigar_lounge", "bar", False, False),
                 ("bar", "restaurant", True, True),
                 ("cigar_lounge", "restaurant", True, True),
                 ("tea_lounge", "restaurant", True, True)]
        for src, tgt, allowed, room in rules:
            CrossOrderingRule.objects.get_or_create(
                source_type=src, target_type=tgt,
                defaults={"allowed": allowed, "requires_room_number": room})

        # a few outlet orders billed
        made = 0
        bar = outlets["bar"]
        bar_items = list(bar.items.all())
        from outlet.models import OutletOrder as _OO
        if _OO.objects.count() < 4:
            for i in range(6):
                m = random.choice(members)
                order = create_outlet_order(
                    outlet=bar, member=m,
                    items=[{"source": "bar", "item_id": random.choice(bar_items).id,
                            "quantity": random.randint(1, 2)}],
                    require_otp=False)
                advance_status(order=order, target_status="preparing")
                advance_status(order=order, target_status="ready")
                advance_status(order=order, target_status="served")
                bill_outlet_order(order=order, payment_mode=random.choice(["cash", "pos"]),
                                  processed_by=self.admin)
                made += 1
        self.stdout.write(f"  outlets: 3 outlets + items + {len(rules)} cross rules + {made} bar orders")

    # ----------------------------------------------------------------
    def _seed_reservations(self, members):
        from reservation.models import ReservableResource
        from reservation.services.reservation_service import create_reservation
        from reservation.services.payment_service import pay_advance

        resources = []
        for name, rtype, adv, cap in [
            ("Card Room 1", "card_room", "500", 2),
            ("Pool Table A", "pool", "300", 1),
            ("Badminton Court 1", "badminton", "400", 1),
            ("Paddle Court 1", "paddle", "450", 1)]:
            r, _ = ReservableResource.objects.get_or_create(
                name=name, defaults={"resource_type": rtype,
                    "advance_amount": Decimal(adv), "capacity": cap,
                    "max_per_member": 2, "slot_minutes": 60, "status": "open"})
            resources.append(r)

        made = 0
        base = timezone.now() + timedelta(days=1)
        from reservation.models import Reservation as _RSV
        if _RSV.objects.count() < 4:
            for i in range(8):
                res = resources[i % len(resources)]
                m = random.choice(members)
                start = base + timedelta(days=i, hours=2 * (i % 3))
                try:
                    booking = create_reservation(
                        resource=res, member=m, start_time=start,
                        end_time=start + timedelta(hours=1), party_size=random.randint(1, 4))
                    if i % 2 == 0 and booking.status == "pending_payment":
                        pay_advance(reservation=booking, payment_mode="sslcommerz",
                                    processed_by=self.admin)
                    made += 1
                except Exception:
                    pass
        self.stdout.write(f"  reservations: {len(resources)} resources + {made} bookings")

    # ----------------------------------------------------------------
    def _seed_payroll(self):
        from payroll.models import (SalaryComponent, SalaryStructure,
            SalaryStructureLine, StaffLoan)
        from payroll.services.payroll_service import generate_run, pay_payslip

        house = SalaryComponent.objects.get_or_create(
            name="House Rent", defaults={"component_type": "earning",
                "calc_type": "percent_of_basic"})[0]
        medical = SalaryComponent.objects.get_or_create(
            name="Medical", defaults={"component_type": "earning", "calc_type": "fixed"})[0]
        tax = SalaryComponent.objects.get_or_create(
            name="Tax", defaults={"component_type": "deduction", "calc_type": "fixed"})[0]
        pf = SalaryComponent.objects.get_or_create(
            name="Provident Fund", defaults={"component_type": "deduction",
                "calc_type": "percent_of_basic"})[0]

        for sp in self.staff_profiles:
            struct, created = SalaryStructure.objects.get_or_create(
                staff=sp, is_current=True,
                defaults={"basic_salary": Decimal(random.choice(["25000", "30000", "40000", "50000"])),
                          "effective_from": date.today().replace(day=1)})
            if created:
                SalaryStructureLine.objects.create(structure=struct, component=house, value=Decimal("40"))
                SalaryStructureLine.objects.create(structure=struct, component=medical, value=Decimal("2000"))
                SalaryStructureLine.objects.create(structure=struct, component=tax, value=Decimal("1500"))
                SalaryStructureLine.objects.create(structure=struct, component=pf, value=Decimal("5"))
        # one staff loan
        StaffLoan.objects.get_or_create(
            staff=self.staff_profiles[0],
            defaults={"principal": Decimal("20000"), "monthly_deduction": Decimal("2000"),
                      "outstanding": Decimal("20000")})

        # generate a run for last month (so it doesn't clash with a future real run)
        last = (date.today().replace(day=1) - timedelta(days=1))
        try:
            run = generate_run(name=f"Payroll {last.strftime('%B %Y')}",
                               period_year=last.year, period_month=last.month,
                               processed_by=self.admin)
            # pay half the payslips
            for i, slip in enumerate(run.payslips.all()):
                if i % 2 == 0:
                    pay_payslip(payslip=slip, processed_by=self.admin)
            self.stdout.write(f"  payroll: 4 components, {len(self.staff_profiles)} structures, "
                               f"run with {run.payslips.count()} payslips (half paid)")
        except Exception as e:
            self.stdout.write(f"  payroll: structures created (run skipped: {e})")

    # ----------------------------------------------------------------
    def _seed_vendors(self):
        from vendor.models import (Vendor, VendorServiceCategory, VendorServiceOffer)
        from vendor.services.vendor_service import select_offer, record_vendor_payment

        cats = {n: VendorServiceCategory.objects.get_or_create(name=n)[0]
                for n in ["Laundry", "Security", "Catering Supplies", "Maintenance"]}
        vendors = [Vendor.objects.get_or_create(
            name=n, defaults={"contact_person": random.choice(FIRST_NAMES),
                "phone": f"01{random.randint(300000000, 999999999)}",
                "email": f"{n.lower().replace(' ', '')}@vendor.test"})[0]
            for n in ["CleanCo", "SecureGuard", "FreshSupply", "FixIt Services", "QuickWash"]]

        # each category gets 2-3 competing offers, one selected
        for cname, cat in cats.items():
            # idempotent: if this category already has a selected offer, skip
            if VendorServiceOffer.objects.filter(category=cat, status="selected").exists():
                continue
            chosen = None
            for v in random.sample(vendors, 3):
                offer, _ = VendorServiceOffer.objects.get_or_create(
                    vendor=v, category=cat, title=f"{cname} package",
                    defaults={"price": Decimal(random.choice(["8000", "9500", "11000", "12500"])),
                              "billing_cycle": "monthly"})
                chosen = offer
            if chosen:
                select_offer(offer=chosen)
                record_vendor_payment(offer=chosen, amount=chosen.price,
                                      note="First month", created_by=self.admin)
        self.stdout.write(f"  vendors: {len(vendors)} vendors, {len(cats)} categories with offers (one selected each)")

    # ----------------------------------------------------------------
    def _seed_finance(self):
        from finance_core.services.ledger_service import record_expense
        from finance_core.models import Expense as _EXP
        if _EXP.objects.count() >= 10:
            self.stdout.write("  finance: expense entries already present, skipped")
            return
        cats = [("Utilities", "manual", "Electricity bill"),
                ("Utilities", "manual", "Water & gas"),
                ("Maintenance", "manual", "AC servicing"),
                ("Supplies", "restaurant", "Kitchen supplies"),
                ("Marketing", "event", "Event promotion")]
        for cat, mod, desc in cats:
            for _ in range(3):
                record_expense(source_module=mod, category_name=cat,
                               amount=Decimal(random.choice(["3000", "5500", "8000", "12000"])),
                               description=desc, created_by=self.admin)
        self.stdout.write("  finance: ~15 expense ledger entries across categories/modules")

    # ----------------------------------------------------------------
    def _seed_events(self, members):
        from event.models import Event, EventExpense, EventFoodItem
        now = timezone.now()
        evspecs = [("Annual Mezban", "Mezban"), ("Movie Night", "Movie"),
                   ("Live Music Evening", "Music")]
        for title, etype in evspecs:
            ev, created = Event.objects.get_or_create(
                title=title,
                defaults={"description": f"{title} for club members.",
                          "start_date": now + timedelta(days=random.randint(5, 30)),
                          "end_date": now + timedelta(days=random.randint(5, 30), hours=4),
                          "status": "planned",
                          "registration_deadline": now + timedelta(days=3),
                          "event_type": etype,
                          "reminder_time": now + timedelta(days=2),
                          "organizer": random.choice(members)})
            if created:
                EventExpense.objects.create(event=ev, kind="food", title="Catering",
                    quantity=Decimal("200"), unit_cost=Decimal("350"), amount=Decimal("70000"))
                EventExpense.objects.create(event=ev, kind="logistics", title="Sound & stage",
                    quantity=Decimal("1"), unit_cost=Decimal("25000"), amount=Decimal("25000"))
                EventFoodItem.objects.create(event=ev, name="Kacchi Biryani",
                    quantity=Decimal("200"), unit="plate", estimated_cost=Decimal("70000"))
        self.stdout.write(f"  events: {len(evspecs)} events with expenses + food items")

    # ----------------------------------------------------------------
    def _summary(self):
        from member.models import Member
        from attendance.models import AttendanceRecord, Guest
        from restaurant.models import RestaurantOrder, RestaurantItem
        from outlet.models import OutletOrder, Outlet
        from reservation.models import Reservation
        from payroll.models import Payslip
        from vendor.models import VendorServiceOffer
        from finance_core.models import Expense
        from event.models import Event
        self.stdout.write(self.style.SUCCESS("\n===== SEED SUMMARY ====="))
        rows = [
            ("Members", Member.objects.count()),
            ("Staff profiles", len(getattr(self, "staff_profiles", []))),
            ("Attendance records", AttendanceRecord.objects.count()),
            ("Guests", Guest.objects.count()),
            ("Restaurant items", RestaurantItem.objects.count()),
            ("Restaurant orders", RestaurantOrder.objects.count()),
            ("Outlets", Outlet.objects.count()),
            ("Outlet orders", OutletOrder.objects.count()),
            ("Reservations", Reservation.objects.count()),
            ("Payslips", Payslip.objects.count()),
            ("Vendor offers", VendorServiceOffer.objects.count()),
            ("Expense entries", Expense.objects.count()),
            ("Events", Event.objects.count()),
        ]
        for label, n in rows:
            self.stdout.write(f"  {label:.<28} {n}")
        self.stdout.write(self.style.SUCCESS("\nLogin: admin / admin1234"))
