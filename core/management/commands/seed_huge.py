"""
HIGH-VOLUME seed data for the Saint Club Limited backend.

This builds on the proven, schema-correct logic in ``seed_demo`` but generates
a *large* and *varied* dataset suitable for load-testing UI lists, pagination,
search, filters, reports and dashboards.

Usage:
    python manage.py seed_huge                       # big defaults
    python manage.py seed_huge --members 1000        # custom volumes
    python manage.py seed_huge --staff 80 --months 12
    python manage.py seed_huge --flush               # wipe seeded data first

Idempotent-ish: it uses get_or_create for catalogue rows and appends
transactional rows (orders/records/payments) up to the requested volume.
Run with --flush for a clean, deterministic large dataset.

Generated (with defaults):
  ~600 members (+ contacts, emails, financial basics)
  ~60 staff (+ salary structures)
  thousands of attendance records across several months
  hundreds of RFID cards + guests
  multiple restaurants & outlets, big menus, hundreds of billed orders
  hundreds of reservations
  several monthly payroll runs (mostly paid)
  many vendors, categories, offers and monthly payments
  hundreds of finance expense ledger entries
  dozens of events with expenses & food items
"""
import random
from datetime import date, timedelta, time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

# Reuse the demo command's proven helpers so we stay schema-correct.
from core.management.commands.seed_demo import (
    Command as DemoCommand, FIRST_NAMES, LAST_NAMES, _tiny_png, PERMISSIONS,
)

User = get_user_model()

# A wider variety pool so big datasets don't look repetitive.
EXTRA_FIRST = ["Adib", "Bushra", "Chayan", "Dalia", "Emon", "Farhana", "Galib",
               "Habib", "Ishrat", "Jamil", "Kamrul", "Labib", "Maliha",
               "Nabil", "Orpita", "Polash", "Quazi", "Rumi", "Samira",
               "Tahmid", "Upoma", "Vaskar", "Wahid", "Xenia", "Yasin", "Zara",
               "Anika", "Borhan", "Chaity", "Didar", "Esha", "Faisal"]
EXTRA_LAST = ["Mridha", "Sarkar", "Talukder", "Mollah", "Sheikh", "Patwary",
              "Majumder", "Biswas", "Sikder", "Pramanik", "Howlader", "Joarder"]

BLOOD = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]


class Command(DemoCommand):
    help = "Seed a HUGE, varied dataset for the club management system."

    def add_arguments(self, parser):
        parser.add_argument("--members", type=int, default=600)
        parser.add_argument("--staff", type=int, default=60)
        parser.add_argument("--months", type=int, default=6,
                            help="How many months of historical activity")
        parser.add_argument("--flush", action="store_true",
                            help="Delete previously seeded data first")

    def handle(self, *args, **opts):
        self.months = max(1, opts["months"])
        self.stdout.write(self.style.WARNING(
            f"Seeding HUGE dataset: {opts['members']} members, "
            f"{opts['staff']} staff, {self.months} months of history..."))
        if opts["flush"]:
            self._flush()

        from django.core.management import call_command
        from member.models import Member
        from attendance.models import StaffProfile

        # Check if seed_accounts has been run by checking if we have member / staff accounts
        member_users = User.objects.filter(username__startswith="member")
        staff_users = User.objects.filter(username__startswith="staff")

        if not member_users.exists() or not staff_users.exists():
            self.stdout.write(self.style.WARNING("Unified accounts not found. Running seed_accounts first..."))
            call_command("seed_accounts", members=opts["members"], staff=opts["staff"])
        else:
            self.stdout.write(self.style.SUCCESS("Existing unified accounts found. Using them for seeding data..."))

        # Load users, members and staff profiles
        self.admin = User.objects.filter(is_superuser=True).first()
        if not self.admin:
            # Fallback or create superuser if not found
            self.admin, _ = User.objects.get_or_create(
                username="admin",
                defaults={"email": "admin@gacl.test", "is_staff": True,
                          "is_superuser": True, "first_name": "Club", "last_name": "Admin"})
            if not self.admin.check_password("admin1234"):
                self.admin.set_password("admin1234")
                self.admin.save()

        self.staff_profiles = list(StaffProfile.objects.all())
        members = list(Member.objects.all())

        # widen the random pools
        FIRST_NAMES.extend(EXTRA_FIRST)
        LAST_NAMES.extend(EXTRA_LAST)

        with transaction.atomic():
            self._seed_choice_models()
            self._seed_attendance_huge(members)
            self._seed_restaurant_huge(members)
            self._seed_outlets_huge(members)
            self._seed_reservations_huge(members)
            self._seed_payroll_huge()
            self._seed_vendors_huge()
            self._seed_finance_huge()
            self._seed_events_huge(members)
        self.stdout.write(self.style.SUCCESS("HUGE seed complete."))
        self._summary()

    def _seed_choice_models(self):
        from core.models import (Gender, MembershipType, InstituteName,
            MembershipStatusChoice, MaritalStatusChoice)

        def safe_get_or_create(model, name, defaults=None):
            obj = model.objects.filter(name__iexact=name).first()
            if obj:
                return obj
            return model.objects.create(name=name, **(defaults or {}))

        self.genders = [safe_get_or_create(Gender, n) for n in ["Male", "Female", "Other"]]
        self.mtypes = [safe_get_or_create(MembershipType, n) for n in ["General", "Life", "Corporate", "Honorary"]]
        self.institutes = [
            safe_get_or_create(InstituteName, n, {"code": f"INST{idx:02d}"})
            for idx, n in enumerate(["Dhaka University", "BUET", "NSU", "BRAC"], start=1)
        ]
        self.mstatus = [safe_get_or_create(MembershipStatusChoice, n) for n in ["Active", "Suspended", "Pending"]]
        self.marital = [safe_get_or_create(MaritalStatusChoice, n) for n in ["Single", "Married"]]

    # ----------------------------------------------------------------
    # Members: override to use Saint-Club prefix + far more variety.
    # ----------------------------------------------------------------
    def _seed_members(self, count):
        from member.models import (Member, MembersFinancialBasics,
                                    ContactNumber, Email)
        members = []
        existing = Member.objects.count()
        for i in range(1, count + 1):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            mid = f"SCL-{i:05d}"
            m, created = Member.objects.get_or_create(
                member_ID=mid,
                defaults={
                    "first_name": fn, "last_name": ln,
                    "date_of_birth": date(1965 + i % 40, (i % 12) + 1,
                                          (i % 27) + 1),
                    "batch_number": f"B{1990 + (i % 33)}",
                    "blood_group": random.choice(BLOOD),
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
                fee = Decimal(random.choice(["50000", "75000", "100000"]))
                paid = Decimal(random.choice(
                    ["50000", "40000", "30000", "75000", "100000"]))
                MembersFinancialBasics.objects.create(
                    member=m, membership_fee=fee,
                    payment_received=min(paid, fee),
                    membership_fee_remaining=max(Decimal("0"), fee - paid),
                    subscription_fee=Decimal(random.choice(["2000", "3000"])),
                    dues_limit=Decimal(random.choice(
                        ["5000", "10000", "15000", "20000"])),
                    status=1)
                ContactNumber.objects.create(
                    member=m,
                    number=f"01{random.randint(300000000, 999999999)}",
                    is_primary=True, status=1)
                # some members get a second number
                if i % 4 == 0:
                    ContactNumber.objects.create(
                        member=m,
                        number=f"01{random.randint(300000000, 999999999)}",
                        is_primary=False, status=1)
                Email.objects.create(
                    member=m, email=f"{fn.lower()}.{ln.lower()}{i}@example.com",
                    is_primary=True, status=1)
            members.append(m)
        self.stdout.write(
            f"  members: {len(members)} total (created this run, "
            f"prior existing {existing})")
        return members

    # ----------------------------------------------------------------
    def _seed_attendance_huge(self, members):
        from attendance.models import RFIDCard, Guest, AttendanceRecord

        # member cards for a large subset
        carded = members[: min(len(members), 400)]
        cards = []
        for idx, m in enumerate(carded):
            card, _ = RFIDCard.objects.get_or_create(
                card_uid=f"CARD-M-{idx:05d}",
                defaults={"card_type": "member", "member": m,
                          "is_assigned": True})
            cards.append(card)

        # staff cards
        for idx, sp in enumerate(getattr(self, "staff_profiles", [])):
            RFIDCard.objects.get_or_create(
                card_uid=f"CARD-S-{idx:04d}",
                defaults={"card_type": "staff", "staff": sp,
                          "is_assigned": True})

        # a pool of unassigned guest-temporary cards
        for idx in range(30):
            RFIDCard.objects.get_or_create(
                card_uid=f"CARD-G-{idx:04d}",
                defaults={"card_type": "guest_temporary", "is_assigned": False})

        # historical attendance records across N months
        rec_target = len(carded) * self.months
        made = 0
        now = timezone.now()
        for n in range(rec_target):
            card = random.choice(cards)
            days_ago = random.randint(0, self.months * 30)
            check_in = now - timedelta(days=days_ago,
                                       hours=random.randint(0, 10),
                                       minutes=random.randint(0, 59))
            checked_out = random.random() < 0.85
            AttendanceRecord.objects.create(
                subject_type="member", member=card.member, card=card,
                check_in=check_in,
                check_out=(check_in + timedelta(hours=random.randint(1, 6)))
                if checked_out else None)
            made += 1

        # many guests, some with temp cards
        hosts = members[:200]
        guest_made = 0
        for i in range(250):
            host = random.choice(hosts)
            g, created = Guest.objects.get_or_create(
                name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                phone=f"01{random.randint(300000000, 999999999)}",
                defaults={"guest_relation": random.choice(
                    ["friend", "family", "colleague", "business"]),
                    "host_type": "member", "host_member": host})
            if created:
                guest_made += 1
        self.stdout.write(
            f"  attendance: {len(cards)} member cards, {made} records, "
            f"{guest_made} guests")

    # ----------------------------------------------------------------
    def _seed_restaurant_huge(self, members):
        from restaurant.models import (
            Restaurant, RestaurantCuisineCategory, RestaurantCategory,
            RestaurantItemCategory, RestaurantItem, RestaurantItemSetting,
            SpicyLevel, RestaurantInventoryItem, RestaurantItemRecipe)
        from restaurant.services.order_service import (
            create_order, advance_kitchen_status)
        from restaurant.services.billing_service import bill_order

        spicy_levels = [SpicyLevel.objects.get_or_create(
            name=n, defaults={"rank": r})[0]
            for r, n in enumerate(["Mild", "Medium", "Hot", "Extra Hot"])]
        icat, _ = RestaurantItemCategory.objects.get_or_create(name="Main Course")
        dcat, _ = RestaurantItemCategory.objects.get_or_create(name="Beverages")
        scat, _ = RestaurantItemCategory.objects.get_or_create(name="Starters")
        ddcat, _ = RestaurantItemCategory.objects.get_or_create(name="Desserts")

        rest_specs = [
            ("Saint Club Main Restaurant", "Continental", "Fine Dining", 150),
            ("Saint Rooftop Grill", "BBQ", "Casual Dining", 80),
            ("Saint Cafe & Bakery", "Cafe", "Quick Service", 60),
        ]
        all_items = []
        for ridx, (rname, cuisine_name, cat_name, cap) in enumerate(rest_specs):
            cuisine, _ = RestaurantCuisineCategory.objects.get_or_create(
                name=cuisine_name)
            rcat, _ = RestaurantCategory.objects.get_or_create(name=cat_name)
            rest, _ = Restaurant.objects.get_or_create(
                name=rname,
                defaults={"cuisine_type": cuisine, "restaurant_type": rcat,
                          "capacity": cap, "status": "open"})
            # short code keeps globally-unique item names distinct per restaurant
            rcode = ["MR", "RG", "CB"][ridx] if ridx < 3 else f"R{ridx}"
            menu = [
                ("Beef Steak", icat, 850, 400, True),
                ("Chicken Biryani", icat, 350, 150, True),
                ("Grilled Fish", icat, 600, 280, True),
                ("Mutton Curry", icat, 550, 260, True),
                ("Prawn Masala", icat, 720, 340, True),
                ("Vegetable Khichuri", icat, 280, 110, True),
                ("Caesar Salad", scat, 320, 120, False),
                ("Chicken Soup", scat, 240, 90, False),
                ("Spring Rolls", scat, 260, 100, True),
                ("Fresh Lime", dcat, 120, 30, False),
                ("Cold Coffee", dcat, 200, 70, False),
                ("Mango Lassi", dcat, 180, 60, False),
                ("Mineral Water", dcat, 50, 15, False),
                ("Chocolate Lava Cake", ddcat, 320, 130, False),
                ("Cheesecake", ddcat, 350, 140, False),
            ]
            for name, cat, price, cost, spicy in menu:
                it, created = RestaurantItem.objects.get_or_create(
                    name=f"{name} [{rcode}]", restaurant=rest,
                    defaults={"category": cat, "unit": "plate",
                              "unit_cost": Decimal(cost),
                              "selling_price": Decimal(price),
                              "availability": True})
                RestaurantItemSetting.objects.get_or_create(
                    item=it, defaults={"spicy_selectable": spicy,
                                       "is_public_show": True})
                all_items.append(it)

            # inventory + recipe per restaurant
            beef = RestaurantInventoryItem.objects.get_or_create(
                name=f"Beef ({rname[:10]})", restaurant=rest,
                defaults={"unit": "kg", "current_quantity": Decimal("120"),
                          "reorder_level": Decimal("20"),
                          "unit_cost": Decimal("700")})[0]
            RestaurantInventoryItem.objects.get_or_create(
                name=f"Rice ({rname[:10]})", restaurant=rest,
                defaults={"unit": "kg", "current_quantity": Decimal("300"),
                          "reorder_level": Decimal("40"),
                          "unit_cost": Decimal("80")})
            first_item = RestaurantItem.objects.filter(restaurant=rest).first()
            if first_item:
                RestaurantItemRecipe.objects.get_or_create(
                    item=first_item, inventory_item=beef,
                    defaults={"quantity_per_unit": Decimal("0.3")})

        # many orders across the lifecycle; ~60% billed (income)
        order_target = 250
        made = 0
        for i in range(order_target):
            rest = random.choice(list(Restaurant.objects.all()))
            rest_items = list(RestaurantItem.objects.filter(restaurant=rest))
            if not rest_items:
                continue
            m = random.choice(members)
            chosen = random.sample(rest_items, k=min(len(rest_items),
                                                     random.randint(1, 4)))
            try:
                order = create_order(
                    restaurant=rest, member=m,
                    items=[{"item_id": it.id,
                            "quantity": random.randint(1, 3)} for it in chosen],
                    serve_location=random.choice(["restaurant", "room"]),
                    room_number=str(random.randint(101, 410)),
                    require_otp=False)
                if i % 5 != 0:
                    advance_kitchen_status(order=order, target_status="preparing")
                    advance_kitchen_status(order=order, target_status="ready")
                    advance_kitchen_status(order=order, target_status="served")
                    bill_order(order=order,
                               payment_mode=random.choice(["cash", "pos", "due"]),
                               processed_by=self.admin)
                made += 1
            except Exception:
                pass
        self.stdout.write(
            f"  restaurant: {len(rest_specs)} restaurants, {len(all_items)} "
            f"items, {made} orders (most billed)")

    # ----------------------------------------------------------------
    def _seed_outlets_huge(self, members):
        from outlet.models import (Outlet, OutletItemCategory, OutletItem,
                                    CrossOrderingRule)
        from outlet.services.order_service import (
            create_outlet_order, advance_status)
        from outlet.services.billing_service import bill_outlet_order

        specs = [
            ("Sky Bar", "bar", [("Red Wine", 1200), ("White Wine", 1100),
                                ("Whiskey", 1500), ("Beer", 600),
                                ("Vodka", 1400), ("Gin & Tonic", 900)]),
            ("Riverside Bar", "bar", [("Mojito", 850), ("Margarita", 950),
                                      ("Old Fashioned", 1300), ("Beer", 600)]),
            ("Tea Lounge", "tea_lounge", [("Green Tea", 150),
                                          ("Cappuccino", 250),
                                          ("Fresh Juice", 200),
                                          ("Masala Chai", 120),
                                          ("Espresso", 180)]),
            ("Garden Tea House", "tea_lounge", [("Oolong Tea", 220),
                                                ("Latte", 260),
                                                ("Iced Tea", 180)]),
            ("Cigar Room", "cigar_lounge", [("Premium Cigar", 2500),
                                            ("Cognac", 3000),
                                            ("Cuban Cigar", 4500)]),
        ]
        outlets_by_type = {}
        for name, otype, prods in specs:
            o, _ = Outlet.objects.get_or_create(
                name=name, defaults={"outlet_type": otype, "capacity": 40,
                                     "status": "open", "admin": self.admin})
            cat, _ = OutletItemCategory.objects.get_or_create(
                name=f"{name} Menu", defaults={"outlet_type": otype})
            for pname, price in prods:
                OutletItem.objects.get_or_create(
                    name=pname, outlet=o,
                    defaults={"category": cat, "selling_price": Decimal(price),
                              "unit_cost": Decimal(price) / 3, "unit": "glass",
                              "is_public_show": True})
            outlets_by_type.setdefault(otype, []).append(o)

        rules = [("bar", "cigar_lounge", True, False),
                 ("cigar_lounge", "bar", False, False),
                 ("bar", "restaurant", True, True),
                 ("cigar_lounge", "restaurant", True, True),
                 ("tea_lounge", "restaurant", True, True),
                 ("tea_lounge", "bar", False, False)]
        for src, tgt, allowed, room in rules:
            CrossOrderingRule.objects.get_or_create(
                source_type=src, target_type=tgt,
                defaults={"allowed": allowed, "requires_room_number": room})

        # many billed bar orders
        made = 0
        bars = outlets_by_type.get("bar", [])
        for i in range(120):
            if not bars:
                break
            bar = random.choice(bars)
            bar_items = list(bar.items.all())
            if not bar_items:
                continue
            m = random.choice(members)
            try:
                order = create_outlet_order(
                    outlet=bar, member=m,
                    items=[{"source": "bar",
                            "item_id": random.choice(bar_items).id,
                            "quantity": random.randint(1, 3)}],
                    require_otp=False)
                advance_status(order=order, target_status="preparing")
                advance_status(order=order, target_status="ready")
                advance_status(order=order, target_status="served")
                bill_outlet_order(order=order,
                                  payment_mode=random.choice(["cash", "pos"]),
                                  processed_by=self.admin)
                made += 1
            except Exception:
                pass
        self.stdout.write(
            f"  outlets: {len(specs)} outlets + items + {len(rules)} cross "
            f"rules + {made} billed bar orders")

    # ----------------------------------------------------------------
    def _seed_reservations_huge(self, members):
        from reservation.models import ReservableResource
        from reservation.services.reservation_service import create_reservation
        from reservation.services.payment_service import pay_advance

        resources = []
        spec = [("Card Room 1", "card_room", "500", 4),
                ("Card Room 2", "card_room", "500", 4),
                ("Pool Table A", "pool", "300", 1),
                ("Pool Table B", "pool", "300", 1),
                ("Badminton Court 1", "badminton", "400", 4),
                ("Badminton Court 2", "badminton", "400", 4),
                ("Paddle Court 1", "paddle", "450", 4),
                ("Paddle Court 2", "paddle", "450", 4)]
        for name, rtype, adv, cap in spec:
            r, _ = ReservableResource.objects.get_or_create(
                name=name, defaults={"resource_type": rtype,
                                     "advance_amount": Decimal(adv),
                                     "capacity": cap, "max_per_member": 3,
                                     "slot_minutes": 60, "status": "open"})
            resources.append(r)

        made = 0
        base = timezone.now() + timedelta(days=1)
        # spread bookings over the next ~45 days, many slots
        for i in range(200):
            res = resources[i % len(resources)]
            m = random.choice(members)
            day_offset = i % 45
            hour = 8 + (i % 12)
            start = (base + timedelta(days=day_offset)).replace(
                hour=hour, minute=0, second=0, microsecond=0)
            try:
                booking = create_reservation(
                    resource=res, member=m, start_time=start,
                    end_time=start + timedelta(hours=1),
                    party_size=random.randint(1, 4))
                if i % 2 == 0 and booking.status == "pending_payment":
                    pay_advance(reservation=booking, payment_mode="sslcommerz",
                                processed_by=self.admin)
                made += 1
            except Exception:
                pass
        self.stdout.write(
            f"  reservations: {len(resources)} resources + {made} bookings")

    # ----------------------------------------------------------------
    def _seed_payroll_huge(self):
        from payroll.models import (SalaryComponent, SalaryStructure,
                                    SalaryStructureLine, StaffLoan)
        from payroll.services.payroll_service import generate_run, pay_payslip

        house = SalaryComponent.objects.get_or_create(
            name="House Rent", defaults={"component_type": "earning",
                                         "calc_type": "percent_of_basic"})[0]
        medical = SalaryComponent.objects.get_or_create(
            name="Medical", defaults={"component_type": "earning",
                                      "calc_type": "fixed"})[0]
        transport = SalaryComponent.objects.get_or_create(
            name="Transport", defaults={"component_type": "earning",
                                        "calc_type": "fixed"})[0]
        tax = SalaryComponent.objects.get_or_create(
            name="Tax", defaults={"component_type": "deduction",
                                  "calc_type": "fixed"})[0]
        pf = SalaryComponent.objects.get_or_create(
            name="Provident Fund", defaults={"component_type": "deduction",
                                             "calc_type": "percent_of_basic"})[0]

        for sp in self.staff_profiles:
            struct, created = SalaryStructure.objects.get_or_create(
                staff=sp, is_current=True,
                defaults={"basic_salary": Decimal(random.choice(
                    ["25000", "30000", "40000", "50000", "65000", "80000"])),
                    "effective_from": date.today().replace(day=1)})
            if created:
                SalaryStructureLine.objects.create(
                    structure=struct, component=house, value=Decimal("40"))
                SalaryStructureLine.objects.create(
                    structure=struct, component=medical, value=Decimal("2000"))
                SalaryStructureLine.objects.create(
                    structure=struct, component=transport, value=Decimal("1500"))
                SalaryStructureLine.objects.create(
                    structure=struct, component=tax, value=Decimal("1500"))
                SalaryStructureLine.objects.create(
                    structure=struct, component=pf, value=Decimal("5"))

        # a few staff loans
        for sp in self.staff_profiles[:5]:
            StaffLoan.objects.get_or_create(
                staff=sp,
                defaults={"principal": Decimal("20000"),
                          "monthly_deduction": Decimal("2000"),
                          "outstanding": Decimal("20000")})

        # generate runs for the previous N months, pay most payslips
        runs_made = 0
        anchor = date.today().replace(day=1)
        for back in range(1, self.months + 1):
            d = anchor
            for _ in range(back):
                d = (d - timedelta(days=1)).replace(day=1)
            try:
                run = generate_run(name=f"Payroll {d.strftime('%B %Y')}",
                                   period_year=d.year, period_month=d.month,
                                   processed_by=self.admin)
                for i, slip in enumerate(run.payslips.all()):
                    if i % 4 != 0:  # ~75% paid
                        pay_payslip(payslip=slip, processed_by=self.admin)
                runs_made += 1
            except Exception:
                pass
        self.stdout.write(
            f"  payroll: 5 components, {len(self.staff_profiles)} structures, "
            f"{runs_made} monthly runs (most paid)")

    # ----------------------------------------------------------------
    def _seed_vendors_huge(self):
        from vendor.models import (Vendor, VendorServiceCategory,
                                   VendorServiceOffer)
        from vendor.services.vendor_service import (
            select_offer, record_vendor_payment)

        cat_names = ["Laundry", "Security", "Catering Supplies", "Maintenance",
                     "Landscaping", "IT Services", "Cleaning", "Transport",
                     "Printing", "Pest Control"]
        cats = {n: VendorServiceCategory.objects.get_or_create(name=n)[0]
                for n in cat_names}

        vendor_names = ["CleanCo", "SecureGuard", "FreshSupply", "FixIt Services",
                        "QuickWash", "GreenScape", "TechBridge", "SparkleClean",
                        "CityMovers", "PrintPro", "SafePest", "EliteCater",
                        "GuardForce", "LaundroMax", "NetServe"]
        vendors = [Vendor.objects.get_or_create(
            name=n, defaults={
                "contact_person": random.choice(FIRST_NAMES),
                "phone": f"01{random.randint(300000000, 999999999)}",
                "email": f"{n.lower().replace(' ', '')}@vendor.test"})[0]
            for n in vendor_names]

        total_payments = 0
        for cname, cat in cats.items():
            if VendorServiceOffer.objects.filter(
                    category=cat, status="selected").exists():
                continue
            chosen = None
            for v in random.sample(vendors, 3):
                offer, _ = VendorServiceOffer.objects.get_or_create(
                    vendor=v, category=cat, title=f"{cname} package",
                    defaults={"price": Decimal(random.choice(
                        ["8000", "9500", "11000", "12500", "15000", "18000"])),
                        "billing_cycle": "monthly"})
                chosen = offer
            if chosen:
                select_offer(offer=chosen)
                # record several months of payments for the selected vendor
                now = timezone.now().date()
                for back in range(self.months):
                    d = now.replace(day=1)
                    for _ in range(back):
                        d = (d - timedelta(days=1)).replace(day=1)
                    try:
                        record_vendor_payment(
                            offer=chosen, amount=chosen.price,
                            note=f"{d.strftime('%B %Y')} bill",
                            created_by=self.admin, reference=f"TXN{random.randint(10000, 99999)}",
                            payment_type="monthly", period_month=d.month,
                            period_year=d.year, paid_on=d)
                        total_payments += 1
                    except Exception:
                        pass
        self.stdout.write(
            f"  vendors: {len(vendors)} vendors, {len(cats)} categories, "
            f"{total_payments} monthly payments")

    # ----------------------------------------------------------------
    def _seed_finance_huge(self):
        from finance_core.services.ledger_service import record_expense
        cats = [("Utilities", "manual", ["Electricity bill", "Water & gas",
                                         "Internet & phone"]),
                ("Maintenance", "manual", ["AC servicing", "Plumbing repair",
                                           "Generator service"]),
                ("Supplies", "restaurant", ["Kitchen supplies", "Cleaning items"]),
                ("Marketing", "event", ["Event promotion", "Social media ads"]),
                ("Salaries", "payroll", ["Monthly payroll"]),
                ("Security", "manual", ["Guard service"]),
                ("Office", "manual", ["Stationery", "Office equipment"])]
        made = 0
        for cat, mod, descs in cats:
            for desc in descs:
                for _ in range(self.months * 2):
                    record_expense(
                        source_module=mod, category_name=cat,
                        amount=Decimal(random.choice(
                            ["3000", "5500", "8000", "12000", "18000", "25000"])),
                        description=desc, created_by=self.admin)
                    made += 1
        self.stdout.write(f"  finance: {made} expense ledger entries")

    # ----------------------------------------------------------------
    def _seed_events_huge(self, members):
        from event.models import Event, EventExpense, EventFoodItem
        now = timezone.now()
        titles = [("Annual Mezban", "Mezban"), ("Movie Night", "Movie"),
                  ("Live Music Evening", "Music"), ("New Year Gala", "Gala"),
                  ("Family Picnic", "Picnic"), ("Cultural Night", "Cultural"),
                  ("Sports Day", "Sports"), ("Charity Dinner", "Dinner"),
                  ("Eid Reunion", "Reunion"), ("Winter Carnival", "Carnival"),
                  ("Book Fair", "Fair"), ("Comedy Night", "Comedy")]
        made = 0
        statuses = ["planned", "ongoing", "completed", "cancelled"]
        for idx, (title, etype) in enumerate(titles):
            # mix of past (completed) and future (planned) events
            past = idx % 2 == 0
            start = now + timedelta(days=random.randint(5, 60)) if not past \
                else now - timedelta(days=random.randint(5, 120))
            ev, created = Event.objects.get_or_create(
                title=title,
                defaults={"description": f"{title} for Saint Club members.",
                          "start_date": start,
                          "end_date": start + timedelta(hours=4),
                          "status": "completed" if past else "planned",
                          "registration_deadline": start - timedelta(days=3),
                          "event_type": etype,
                          "reminder_time": start - timedelta(days=2),
                          "organizer": random.choice(members)})
            if created:
                EventExpense.objects.create(
                    event=ev, kind="food", title="Catering",
                    quantity=Decimal("200"), unit_cost=Decimal("350"),
                    amount=Decimal("70000"))
                EventExpense.objects.create(
                    event=ev, kind="logistics", title="Sound & stage",
                    quantity=Decimal("1"), unit_cost=Decimal("25000"),
                    amount=Decimal("25000"))
                EventExpense.objects.create(
                    event=ev, kind="decor", title="Decoration",
                    quantity=Decimal("1"), unit_cost=Decimal("15000"),
                    amount=Decimal("15000"))
                EventFoodItem.objects.create(
                    event=ev, name="Kacchi Biryani", quantity=Decimal("200"),
                    unit="plate", estimated_cost=Decimal("70000"))
                EventFoodItem.objects.create(
                    event=ev, name="Borhani", quantity=Decimal("200"),
                    unit="glass", estimated_cost=Decimal("10000"))
                made += 1
        self.stdout.write(
            f"  events: {made} events with expenses + food items")
