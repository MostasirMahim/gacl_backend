import random
from datetime import time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from outlet.models import (
    Outlet,
    OutletItemCategory,
    OutletItem,
    CrossOrderingRule,
    OutletInventoryItem,
    OutletItemRecipe,
    OutletOrder,
    OutletOrderItem,
)
from member.models import Member
from outlet.services.order_service import create_outlet_order, advance_status
from outlet.services.billing_service import bill_outlet_order

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds database with comprehensive Outlets (Bars, Tea Lounges, Cigar Lounges), categories, items, inventory, recipes, cross-ordering rules, and sample orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orders",
            type=int,
            default=25,
            help="Number of realistic orders to generate across various lifecycle states (default: 25).",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Wipe previously seeded outlet items, inventory, recipes, and rules before seeding.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write(self.style.WARNING("  GACL / SAINT CLUB — OUTLETS DATA SEEDING"))
        self.stdout.write(self.style.WARNING("=" * 70))

        num_orders = options.get("orders", 25)
        flush = options.get("flush", False)

        # 1. Identify Admin User
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(username="admin").first()
        if not admin_user:
            admin_user = User.objects.first()

        if not admin_user:
            self.stdout.write(
                self.style.ERROR(
                    "No user account found. Please run `python manage.py bootstrap_admin` first."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Assigning outlet administration to user: {admin_user.username}")
        )

        # 2. Flush if requested
        if flush:
            self.stdout.write(self.style.WARNING("Flushing existing outlet operational records..."))
            OutletItemRecipe.objects.all().delete()
            OutletInventoryItem.objects.all().delete()
            OutletOrderItem.objects.all().delete()
            OutletOrder.objects.all().delete()
            OutletItem.objects.all().delete()
            CrossOrderingRule.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Existing outlet operational records flushed."))

        # 3. Create / Update Venues (Outlets)
        outlets_data = [
            {
                "name": "Sky Bar",
                "outlet_type": "bar",
                "description": "Rooftop lounge overlooking the city skyline, serving signature cocktails, aged single malts, and vintage wines.",
                "address": "Level 5, Club Clubhouse Rooftop",
                "phone": "+880 1711 000101",
                "capacity": 65,
                "status": "open",
                "opening_time": time(16, 0),
                "closing_time": time(1, 0),
            },
            {
                "name": "Riverside Bar",
                "outlet_type": "bar",
                "description": "Serene outdoor deck bar by the lake, perfect for evening draft beers, spritzers, and casual mixers.",
                "address": "Ground Deck, East Promenade",
                "phone": "+880 1711 000102",
                "capacity": 80,
                "status": "open",
                "opening_time": time(15, 0),
                "closing_time": time(23, 30),
            },
            {
                "name": "Tea Lounge",
                "outlet_type": "tea_lounge",
                "description": "Heritage British & Asian tea room offering artisan loose-leaf teas, organic matcha, barista espresso, and patisserie.",
                "address": "1st Floor, Heritage Wing",
                "phone": "+880 1711 000103",
                "capacity": 45,
                "status": "open",
                "opening_time": time(8, 0),
                "closing_time": time(21, 0),
            },
            {
                "name": "Garden Tea House",
                "outlet_type": "tea_lounge",
                "description": "Botanical pavilion serving organic herbal infusions, iced blends, artisan lattes, and afternoon savories.",
                "address": "North Botanical Pavilion",
                "phone": "+880 1711 000104",
                "capacity": 35,
                "status": "open",
                "opening_time": time(9, 0),
                "closing_time": time(19, 30),
            },
            {
                "name": "Cigar Room",
                "outlet_type": "cigar_lounge",
                "description": "Exclusive VIP sanctuary featuring state-of-the-art climate humidor, rare hand-rolled cigars, and vintage cognacs.",
                "address": "Mezzanine Level, Members Private Wing",
                "phone": "+880 1711 000105",
                "capacity": 30,
                "status": "open",
                "opening_time": time(17, 0),
                "closing_time": time(2, 0),
            },
        ]

        outlets_map = {}
        for o_info in outlets_data:
            outlet, created = Outlet.objects.update_or_create(
                name=o_info["name"],
                defaults={
                    "outlet_type": o_info["outlet_type"],
                    "description": o_info["description"],
                    "address": o_info["address"],
                    "phone": o_info["phone"],
                    "capacity": o_info["capacity"],
                    "status": o_info["status"],
                    "opening_time": o_info["opening_time"],
                    "closing_time": o_info["closing_time"],
                    "admin": admin_user,
                    "is_active": True,
                },
            )
            outlets_map[outlet.name] = outlet
            state = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  [{state}] Outlet: {outlet.name} ({outlet.outlet_type})"))

        # 4. Create Item Categories
        categories_data = [
            # Bars
            ("Fine Wines & Champagne", "bar"),
            ("Spirits & Single Malts", "bar"),
            ("Cocktails & Long Drinks", "bar"),
            ("Craft Beers & Cider", "bar"),
            ("Sky Bar Menu", "bar"),
            ("Riverside Bar Menu", "bar"),
            # Tea Lounges
            ("Artisan Loose Leaf Teas", "tea_lounge"),
            ("Specialty Coffee & Espresso", "tea_lounge"),
            ("Cold Brews & Iced Blends", "tea_lounge"),
            ("Fresh Pressed Juices", "tea_lounge"),
            ("Tea Lounge Menu", "tea_lounge"),
            ("Garden Tea House Menu", "tea_lounge"),
            # Cigar Lounge
            ("Hand-Rolled Premium Cigars", "cigar_lounge"),
            ("Aged Cognacs & Brandies", "cigar_lounge"),
            ("Rare Fortified Ports", "cigar_lounge"),
            ("Cigar Room Menu", "cigar_lounge"),
        ]

        category_map = {}
        for cat_name, otype in categories_data:
            cat, _ = OutletItemCategory.objects.update_or_create(
                name=cat_name,
                outlet_type=otype,
                defaults={"is_active": True},
            )
            category_map[(cat_name, otype)] = cat

        self.stdout.write(self.style.SUCCESS(f"  Configured {len(category_map)} item categories."))

        # 5. Create Menu Items
        items_data = [
            # ── SKY BAR ITEMS ──
            {
                "outlet": "Sky Bar",
                "name": "Red Wine",
                "category": "Fine Wines & Champagne",
                "unit": "Glass",
                "unit_cost": Decimal("400.00"),
                "selling_price": Decimal("1200.00"),
                "description": "Selected Chilean Cabernet Sauvignon vintage with blackberry and oak notes.",
            },
            {
                "outlet": "Sky Bar",
                "name": "White Wine",
                "category": "Fine Wines & Champagne",
                "unit": "Glass",
                "unit_cost": Decimal("380.00"),
                "selling_price": Decimal("1100.00"),
                "description": "Crisp Marlborough Sauvignon Blanc with citrus undertones.",
            },
            {
                "outlet": "Sky Bar",
                "name": "Whiskey",
                "category": "Spirits & Single Malts",
                "unit": "Peg (60ml)",
                "unit_cost": Decimal("500.00"),
                "selling_price": Decimal("1500.00"),
                "description": "12-Year-Old Highland Single Malt served neat or on hand-carved ice.",
            },
            {
                "outlet": "Sky Bar",
                "name": "Beer",
                "category": "Craft Beers & Cider",
                "unit": "Pint",
                "unit_cost": Decimal("200.00"),
                "selling_price": Decimal("600.00"),
                "description": "Chilled European Premium Lager on draft.",
            },
            {
                "outlet": "Sky Bar",
                "name": "Vodka",
                "category": "Spirits & Single Malts",
                "unit": "Peg (60ml)",
                "unit_cost": Decimal("450.00"),
                "selling_price": Decimal("1400.00"),
                "description": "Triple-distilled wheat vodka served chilled with lemon twist.",
            },
            {
                "outlet": "Sky Bar",
                "name": "Gin & Tonic",
                "category": "Cocktails & Long Drinks",
                "unit": "Highball",
                "unit_cost": Decimal("300.00"),
                "selling_price": Decimal("900.00"),
                "description": "London Dry Gin with botanical Indian tonic and fresh cucumber ribbon.",
            },
            {
                "outlet": "Sky Bar",
                "name": "Skyline Spritz",
                "category": "Cocktails & Long Drinks",
                "unit": "Glass",
                "unit_cost": Decimal("350.00"),
                "selling_price": Decimal("1050.00"),
                "description": "Prosecco, Italian bitter liqueur, soda splash, and fresh orange slice.",
            },

            # ── RIVERSIDE BAR ITEMS ──
            {
                "outlet": "Riverside Bar",
                "name": "Mojito",
                "category": "Cocktails & Long Drinks",
                "unit": "Tall Glass",
                "unit_cost": Decimal("280.00"),
                "selling_price": Decimal("850.00"),
                "description": "White rum, muddled garden spearmint, brown sugar, lime juice, and club soda.",
            },
            {
                "outlet": "Riverside Bar",
                "name": "Margarita",
                "category": "Cocktails & Long Drinks",
                "unit": "Coupette",
                "unit_cost": Decimal("320.00"),
                "selling_price": Decimal("950.00"),
                "description": "Blue Agave Reposado tequila, triple sec, fresh lime juice with sea salt rim.",
            },
            {
                "outlet": "Riverside Bar",
                "name": "Old Fashioned",
                "category": "Cocktails & Long Drinks",
                "unit": "Rocks Glass",
                "unit_cost": Decimal("450.00"),
                "selling_price": Decimal("1300.00"),
                "description": "Bourbon whiskey, Angostura aromatic bitters, cane sugar cube, and flamed orange peel.",
            },
            {
                "outlet": "Riverside Bar",
                "name": "Beer",
                "category": "Craft Beers & Cider",
                "unit": "Pint",
                "unit_cost": Decimal("200.00"),
                "selling_price": Decimal("600.00"),
                "description": "Crisp Golden Pilsner served chilled in frozen glassware.",
            },
            {
                "outlet": "Riverside Bar",
                "name": "Riverside Sunset",
                "category": "Cocktails & Long Drinks",
                "unit": "Highball",
                "unit_cost": Decimal("290.00"),
                "selling_price": Decimal("880.00"),
                "description": "Vodka, cranberry nectar, peach schnapps, and passionfruit foam.",
            },

            # ── TEA LOUNGE ITEMS ──
            {
                "outlet": "Tea Lounge",
                "name": "Green Tea",
                "category": "Artisan Loose Leaf Teas",
                "unit": "Pot (400ml)",
                "unit_cost": Decimal("40.00"),
                "selling_price": Decimal("150.00"),
                "description": "Organic Japanese Sencha green tea with subtle grassy sweetness.",
            },
            {
                "outlet": "Tea Lounge",
                "name": "Cappuccino",
                "category": "Specialty Coffee & Espresso",
                "unit": "Cup (250ml)",
                "unit_cost": Decimal("70.00"),
                "selling_price": Decimal("250.00"),
                "description": "Double espresso shot layered with silky steamed milk and dense micro-foam.",
            },
            {
                "outlet": "Tea Lounge",
                "name": "Fresh Juice",
                "category": "Fresh Pressed Juices",
                "unit": "Glass",
                "unit_cost": Decimal("60.00"),
                "selling_price": Decimal("200.00"),
                "description": "100% freshly squeezed seasonal orange, pineapple, or watermelon juice.",
            },
            {
                "outlet": "Tea Lounge",
                "name": "Masala Chai",
                "category": "Artisan Loose Leaf Teas",
                "unit": "Kulhar Pot",
                "unit_cost": Decimal("30.00"),
                "selling_price": Decimal("120.00"),
                "description": "Traditional Assam tea slow-brewed with fresh cardamom, cinnamon, and whole milk.",
            },
            {
                "outlet": "Tea Lounge",
                "name": "Espresso",
                "category": "Specialty Coffee & Espresso",
                "unit": "Single Shot",
                "unit_cost": Decimal("50.00"),
                "selling_price": Decimal("180.00"),
                "description": "Intense dark-roast single origin Arabica with rich golden crema.",
            },

            # ── GARDEN TEA HOUSE ITEMS ──
            {
                "outlet": "Garden Tea House",
                "name": "Oolong Tea",
                "category": "Artisan Loose Leaf Teas",
                "unit": "Pot (400ml)",
                "unit_cost": Decimal("60.00"),
                "selling_price": Decimal("220.00"),
                "description": "Roasted Formosa Oolong tea with smooth floral notes.",
            },
            {
                "outlet": "Garden Tea House",
                "name": "Latte",
                "category": "Specialty Coffee & Espresso",
                "unit": "Glass Mug",
                "unit_cost": Decimal("80.00"),
                "selling_price": Decimal("260.00"),
                "description": "Espresso topped with creamy steamed milk and artisan latte art.",
            },
            {
                "outlet": "Garden Tea House",
                "name": "Iced Tea",
                "category": "Cold Brews & Iced Blends",
                "unit": "Tall Glass",
                "unit_cost": Decimal("45.00"),
                "selling_price": Decimal("180.00"),
                "description": "Slow cold-brewed Darjeeling black tea served with lemon slices and crushed ice.",
            },
            {
                "outlet": "Garden Tea House",
                "name": "Matcha Blossom Latte",
                "category": "Artisan Loose Leaf Teas",
                "unit": "Cup (250ml)",
                "unit_cost": Decimal("90.00"),
                "selling_price": Decimal("280.00"),
                "description": "Ceremonial Uji matcha whisked with oat milk and vanilla bean extract.",
            },

            # ── CIGAR ROOM ITEMS ──
            {
                "outlet": "Cigar Room",
                "name": "Premium Cigar",
                "category": "Hand-Rolled Premium Cigars",
                "unit": "Single Stick",
                "unit_cost": Decimal("800.00"),
                "selling_price": Decimal("2500.00"),
                "description": "Handcrafted Dominican Toro with Connecticut Shade wrapper, medium body.",
            },
            {
                "outlet": "Cigar Room",
                "name": "Cognac",
                "category": "Aged Cognacs & Brandies",
                "unit": "Snifter (60ml)",
                "unit_cost": Decimal("1000.00"),
                "selling_price": Decimal("3000.00"),
                "description": "Aged French VSOP Cognac with complex candied apricot and toasted oak aroma.",
            },
            {
                "outlet": "Cigar Room",
                "name": "Cuban Cigar",
                "category": "Hand-Rolled Premium Cigars",
                "unit": "Single Stick",
                "unit_cost": Decimal("1500.00"),
                "selling_price": Decimal("4500.00"),
                "description": "Authentic Cuban Robusto with rich cedarwood and cocoa bean profiles.",
            },
            {
                "outlet": "Cigar Room",
                "name": "Vintage Port Wine",
                "category": "Rare Fortified Ports",
                "unit": "Glass (90ml)",
                "unit_cost": Decimal("600.00"),
                "selling_price": Decimal("1800.00"),
                "description": "Tawny 20-year Port from Douro Valley, perfect accompaniment for full-bodied cigars.",
            },
        ]

        created_items = []
        for item_data in items_data:
            outlet = outlets_map[item_data["outlet"]]
            cat = category_map.get((item_data["category"], outlet.outlet_type))
            if not cat:
                cat = category_map.get((f"{outlet.name} Menu", outlet.outlet_type))

            item, created = OutletItem.objects.update_or_create(
                name=item_data["name"],
                outlet=outlet,
                defaults={
                    "category": cat,
                    "unit": item_data["unit"],
                    "unit_cost": item_data["unit_cost"],
                    "selling_price": item_data["selling_price"],
                    "description": item_data["description"],
                    "availability": True,
                    "is_public_show": True,
                    "is_active": True,
                },
            )
            created_items.append(item)

        self.stdout.write(self.style.SUCCESS(f"  Configured {len(created_items)} outlet menu items."))

        # 6. Create Cross-Ordering Rules
        rules_specs = [
            ("bar", "cigar_lounge", True, False),
            ("cigar_lounge", "bar", False, False),
            ("bar", "restaurant", True, True),
            ("cigar_lounge", "restaurant", True, True),
            ("tea_lounge", "restaurant", True, True),
            ("tea_lounge", "bar", False, False),
        ]

        for src, tgt, allowed, req_room in rules_specs:
            CrossOrderingRule.objects.update_or_create(
                source_type=src,
                target_type=tgt,
                defaults={
                    "allowed": allowed,
                    "requires_room_number": req_room,
                    "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"  Configured {len(rules_specs)} cross-ordering physical boundary rules."))

        # 7. Create Raw Inventory Items & Reorder Levels
        inventory_specs = [
            # Sky Bar Stock
            ("Sky Bar", "Chilean Cabernet Sauvignon", "Bottle", Decimal("42.0"), Decimal("12.0"), Decimal("750.00")),
            ("Sky Bar", "Marlborough Sauvignon Blanc", "Bottle", Decimal("36.0"), Decimal("10.0"), Decimal("700.00")),
            ("Sky Bar", "Highland Single Malt Scotch", "Litre", Decimal("18.5"), Decimal("5.0"), Decimal("2200.00")),
            ("Sky Bar", "London Dry Gin", "Litre", Decimal("14.0"), Decimal("4.0"), Decimal("1500.00")),
            ("Sky Bar", "Indian Botanical Tonic", "Can (330ml)", Decimal("120.0"), Decimal("30.0"), Decimal("65.00")),
            ("Sky Bar", "Draft Lager Keg", "Keg (50L)", Decimal("4.0"), Decimal("2.0"), Decimal("8500.00")),

            # Riverside Bar Stock
            ("Riverside Bar", "White Rum (Bacardi)", "Litre", Decimal("16.0"), Decimal("4.0"), Decimal("1400.00")),
            ("Riverside Bar", "Reposado Blue Agave Tequila", "Litre", Decimal("11.0"), Decimal("3.0"), Decimal("1900.00")),
            ("Riverside Bar", "Bourbon Whiskey (Maker's Mark)", "Litre", Decimal("9.5"), Decimal("3.0"), Decimal("2100.00")),
            ("Riverside Bar", "Fresh Mint Leaves", "Bunch", Decimal("25.0"), Decimal("10.0"), Decimal("15.00")),
            ("Riverside Bar", "Lime Juice / Fresh Limes", "Kg", Decimal("18.0"), Decimal("5.0"), Decimal("80.00")),

            # Tea Lounge Stock
            ("Tea Lounge", "Organic Sencha Green Tea", "Kg", Decimal("8.5"), Decimal("2.0"), Decimal("1200.00")),
            ("Tea Lounge", "Dark Roast Arabica Coffee Beans", "Kg", Decimal("22.0"), Decimal("5.0"), Decimal("950.00")),
            ("Tea Lounge", "Whole Dairy Milk", "Litre", Decimal("45.0"), Decimal("15.0"), Decimal("85.00")),
            ("Tea Lounge", "Assam CTC Tea Blend", "Kg", Decimal("15.0"), Decimal("4.0"), Decimal("450.00")),
            ("Tea Lounge", "Fresh Oranges", "Kg", Decimal("35.0"), Decimal("10.0"), Decimal("120.00")),

            # Garden Tea House Stock
            ("Garden Tea House", "Formosa Roasted Oolong Tea", "Kg", Decimal("6.0"), Decimal("2.0"), Decimal("1600.00")),
            ("Garden Tea House", "Ceremonial Uji Matcha Powder", "Kg", Decimal("3.5"), Decimal("1.0"), Decimal("3800.00")),
            ("Garden Tea House", "Oat Milk Barista Edition", "Litre", Decimal("28.0"), Decimal("8.0"), Decimal("180.00")),

            # Cigar Room Stock
            ("Cigar Room", "Dominican Toro Hand-Rolled Sticks", "Single Stick", Decimal("85.0"), Decimal("20.0"), Decimal("800.00")),
            ("Cigar Room", "Cuban Robusto Hand-Rolled Sticks", "Single Stick", Decimal("52.0"), Decimal("15.0"), Decimal("1500.00")),
            ("Cigar Room", "French VSOP Cognac", "Litre", Decimal("12.0"), Decimal("3.0"), Decimal("3500.00")),
            ("Cigar Room", "Tawny 20-Year Vintage Port", "Bottle", Decimal("19.0"), Decimal("5.0"), Decimal("2600.00")),
        ]

        inventory_map = {}
        for out_name, iname, unit, qty, reorder, cost in inventory_specs:
            outlet = outlets_map[out_name]
            inv_item, _ = OutletInventoryItem.objects.update_or_create(
                name=iname,
                outlet=outlet,
                defaults={
                    "unit": unit,
                    "current_quantity": qty,
                    "reorder_level": reorder,
                    "unit_cost": cost,
                    "is_active": True,
                },
            )
            inventory_map[(out_name, iname)] = inv_item

        self.stdout.write(self.style.SUCCESS(f"  Configured {len(inventory_map)} raw inventory ledger items with reorder triggers."))

        # 8. Create Recipe Lines
        recipe_specs = [
            ("Sky Bar", "Gin & Tonic", "London Dry Gin", Decimal("0.060")),
            ("Sky Bar", "Gin & Tonic", "Indian Botanical Tonic", Decimal("1.000")),
            ("Sky Bar", "Whiskey", "Highland Single Malt Scotch", Decimal("0.060")),
            ("Riverside Bar", "Mojito", "White Rum (Bacardi)", Decimal("0.060")),
            ("Riverside Bar", "Margarita", "Reposado Blue Agave Tequila", Decimal("0.060")),
            ("Riverside Bar", "Old Fashioned", "Bourbon Whiskey (Maker's Mark)", Decimal("0.060")),
            ("Tea Lounge", "Cappuccino", "Dark Roast Arabica Coffee Beans", Decimal("0.018")),
            ("Tea Lounge", "Cappuccino", "Whole Dairy Milk", Decimal("0.180")),
            ("Tea Lounge", "Green Tea", "Organic Sencha Green Tea", Decimal("0.008")),
            ("Garden Tea House", "Oolong Tea", "Formosa Roasted Oolong Tea", Decimal("0.008")),
            ("Garden Tea House", "Matcha Blossom Latte", "Ceremonial Uji Matcha Powder", Decimal("0.006")),
            ("Cigar Room", "Premium Cigar", "Dominican Toro Hand-Rolled Sticks", Decimal("1.000")),
            ("Cigar Room", "Cuban Cigar", "Cuban Robusto Hand-Rolled Sticks", Decimal("1.000")),
            ("Cigar Room", "Cognac", "French VSOP Cognac", Decimal("0.060")),
        ]

        recipe_count = 0
        for out_name, item_name, inv_name, qty_per_unit in recipe_specs:
            outlet = outlets_map[out_name]
            item = OutletItem.objects.filter(name=item_name, outlet=outlet).first()
            inv_item = inventory_map.get((out_name, inv_name))
            if item and inv_item:
                OutletItemRecipe.objects.update_or_create(
                    item=item,
                    inventory_item=inv_item,
                    defaults={"quantity_per_unit": qty_per_unit, "is_active": True},
                )
                recipe_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Configured {recipe_count} recipe ingredient deduction formulas."))

        # 9. Create Sample Orders Across Lifecycle States
        members = list(Member.objects.filter(is_active=True)[:30])
        if not members:
            self.stdout.write(self.style.WARNING("  No active members found; skipping order seeding. (Run `seed_accounts` first to seed members)."))
            return

        orders_created = 0
        orders_preparing = 0
        orders_billed = 0

        target_outlets = list(outlets_map.values())

        for idx in range(num_orders):
            outlet = random.choice(target_outlets)
            outlet_items = list(outlet.items.filter(availability=True))
            if not outlet_items:
                continue

            member = random.choice(members)
            selected_item = random.choice(outlet_items)
            qty = random.randint(1, 3)

            room_num = f"Room {random.randint(101, 320)}" if outlet.outlet_type == "cigar_lounge" else ""

            try:
                with transaction.atomic():
                    order = create_outlet_order(
                        outlet=outlet,
                        member=member,
                        items=[
                            {
                                "source": outlet.outlet_type,
                                "item_id": selected_item.id,
                                "quantity": qty,
                                "note": "Seeded club demonstration order",
                            }
                        ],
                        placed_by=random.choice(["member", "waiter"]),
                        room_number=room_num,
                        require_otp=False,
                    )
                    orders_created += 1

                    # Vary order lifecycle statuses
                    status_choice = idx % 4
                    if status_choice == 0:
                        # Stays 'confirmed'
                        pass
                    elif status_choice == 1:
                        # In Preparation Queue (visible in KDS)
                        advance_status(order=order, target_status="preparing")
                        orders_preparing += 1
                    elif status_choice == 2:
                        # Ready for delivery
                        advance_status(order=order, target_status="preparing")
                        advance_status(order=order, target_status="ready")
                    elif status_choice == 3:
                        # Served and Billed with Invoice / Ledger Entry
                        advance_status(order=order, target_status="preparing")
                        advance_status(order=order, target_status="ready")
                        advance_status(order=order, target_status="served")
                        bill_outlet_order(
                            order=order,
                            payment_mode=random.choice(["cash", "pos", "due"]),
                            processed_by=admin_user,
                        )
                        orders_billed += 1
            except Exception as e:
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"  Generated {orders_created} sample orders: "
                f"{orders_preparing} in active preparation queue, {orders_billed} settled & billed."
            )
        )

        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write(self.style.SUCCESS("  OUTLETS DATA SEEDING COMPLETED SUCCESSFULLY!"))
        self.stdout.write(self.style.WARNING("=" * 70))
