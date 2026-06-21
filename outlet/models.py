from django.db import models
from django.conf import settings
from django.utils import timezone
from member_financial_management.utils.managers import ActiveManager


class OutletBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# ============================================================
# OUTLET = generic bar / tea lounge / cigar lounge.
# One app, distinguished by `outlet_type`. Each outlet has its own
# admin (a CustomUser) who posts its menu items.
# ============================================================
class Outlet(OutletBaseModel):
    OUTLET_TYPE_CHOICES = [
        ("bar", "bar"),
        ("tea_lounge", "tea_lounge"),
        ("cigar_lounge", "cigar_lounge"),
    ]
    STATUS_CHOICES = [
        ("open", "open"),
        ("closed", "closed"),
    ]
    name = models.CharField(max_length=300, unique=True)
    outlet_type = models.CharField(
        max_length=20, choices=OUTLET_TYPE_CHOICES, db_index=True)
    description = models.TextField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=14, blank=True, default="")
    capacity = models.IntegerField(default=50)
    status = models.CharField(max_length=6, choices=STATUS_CHOICES, default="open")
    opening_time = models.TimeField(blank=True, null=True, default=None)
    closing_time = models.TimeField(blank=True, null=True, default=None)

    # the admin who manages/posts this outlet's menu
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="managed_outlets")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.name} ({self.outlet_type})"


class OutletItemCategory(OutletBaseModel):
    name = models.CharField(max_length=300)
    outlet_type = models.CharField(
        max_length=20, choices=Outlet.OUTLET_TYPE_CHOICES, blank=True, default="")

    class Meta:
        unique_together = ("name", "outlet_type")

    def __str__(self):
        return self.name


class OutletItem(OutletBaseModel):
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    unit = models.CharField(max_length=50, blank=True, default="")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    availability = models.BooleanField(default=True)
    # restaurant-admin-style controls
    spicy_selectable = models.BooleanField(default=False)
    is_public_show = models.BooleanField(default=False)

    category = models.ForeignKey(
        OutletItemCategory, on_delete=models.PROTECT, related_name="items")
    outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name="items")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.name} @ {self.outlet.name}"


class OutletItemMedia(OutletBaseModel):
    image = models.ImageField(upload_to="outlet/items/")
    item = models.ForeignKey(
        OutletItem, on_delete=models.CASCADE, related_name="media")

    def __str__(self):
        return self.item.name


# ------------------------------------------------------------
# Cross-outlet ordering rules.
# Captures: "from bar you can order cigar-lounge items", "from cigar
# lounge you CANNOT order bar items", "any outlet can order restaurant
# food but must supply a room number", etc. Fully data-driven so the
# club can change policy from the admin without code changes.
# ------------------------------------------------------------
class CrossOrderingRule(OutletBaseModel):
    # the outlet the member is physically sitting in
    source_type = models.CharField(
        max_length=20,
        help_text="bar / tea_lounge / cigar_lounge")
    # what they want to order from: an outlet type, or 'restaurant'
    target_type = models.CharField(
        max_length=20,
        help_text="bar / tea_lounge / cigar_lounge / restaurant")
    allowed = models.BooleanField(default=True)
    requires_room_number = models.BooleanField(default=False)

    class Meta:
        unique_together = ("source_type", "target_type")

    def __str__(self):
        state = "allow" if self.allowed else "deny"
        return f"{self.source_type} -> {self.target_type}: {state}"


class OutletOrder(OutletBaseModel):
    ORDER_STATUS_CHOICES = [
        ("pending_otp", "pending_otp"),
        ("confirmed", "confirmed"),
        ("preparing", "preparing"),
        ("ready", "ready"),
        ("served", "served"),
        ("billed", "billed"),
        ("cancelled", "cancelled"),
    ]
    PLACED_BY_CHOICES = [
        ("member", "member"),
        ("waiter", "waiter"),
    ]

    order_number = models.CharField(max_length=60, unique=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=ORDER_STATUS_CHOICES, default="pending_otp", db_index=True)
    placed_by = models.CharField(
        max_length=15, choices=PLACED_BY_CHOICES, default="member")

    # where the member is sitting (the outlet that took the order)
    outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name="orders")
    # room number, required for cross-ordering restaurant food into an outlet
    room_number = models.CharField(max_length=30, blank=True, default="")

    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")

    otp_code = models.CharField(max_length=6, blank=True, default="")
    otp_verified = models.BooleanField(default=False)
    otp_sent_at = models.DateTimeField(blank=True, null=True, default=None)
    confirmed_at = models.DateTimeField(blank=True, null=True, default=None)

    member = models.ForeignKey(
        "member.Member", on_delete=models.PROTECT, related_name="outlet_orders")
    guest = models.ForeignKey(
        "attendance.Guest", on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="outlet_orders")
    waiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="waiter_outlet_orders")
    invoice = models.ForeignKey(
        "member_financial_management.Invoice", on_delete=models.SET_NULL,
        blank=True, null=True, default=None, related_name="outlet_orders")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number


class OutletOrderItem(OutletBaseModel):
    """
    A line in an outlet order. The item may belong to THIS outlet or, when
    cross-ordering is allowed, to another outlet or the restaurant. Exactly
    one of outlet_item / restaurant_item is set.
    """
    order = models.ForeignKey(
        OutletOrder, on_delete=models.CASCADE, related_name="items")
    outlet_item = models.ForeignKey(
        OutletItem, on_delete=models.PROTECT, blank=True, null=True, default=None,
        related_name="order_items")
    restaurant_item = models.ForeignKey(
        "restaurant.RestaurantItem", on_delete=models.PROTECT, blank=True, null=True,
        default=None, related_name="outlet_order_items")

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    spicy_level = models.ForeignKey(
        "restaurant.SpicyLevel", on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="outlet_order_items")
    note = models.CharField(max_length=300, blank=True, default="")
    # which outlet/source this line was ordered from
    source_type = models.CharField(max_length=20, blank=True, default="")

    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def item_name(self):
        if self.outlet_item_id:
            return self.outlet_item.name
        if self.restaurant_item_id:
            return self.restaurant_item.name
        return ""

    def __str__(self):
        return f"{self.item_name} x{self.quantity}"


# ---------------- Inventory (per outlet) ----------------
class OutletInventoryItem(OutletBaseModel):
    name = models.CharField(max_length=300)
    unit = models.CharField(max_length=50)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name="inventory_items")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        unique_together = ("name", "outlet")

    @property
    def is_low(self):
        return self.current_quantity <= self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.outlet.name})"


class OutletInventoryTransaction(OutletBaseModel):
    MOVEMENT_CHOICES = [("in", "in"), ("out", "out")]
    inventory_item = models.ForeignKey(
        OutletInventoryItem, on_delete=models.PROTECT, related_name="movements")
    movement = models.CharField(max_length=3, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=255, blank=True, default="")
    order = models.ForeignKey(
        OutletOrder, on_delete=models.SET_NULL, blank=True, null=True, default=None,
        related_name="inventory_movements")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="outlet_inventory_movements")

    def __str__(self):
        return f"{self.movement} {self.quantity} {self.inventory_item.name}"


class OutletItemRecipe(OutletBaseModel):
    item = models.ForeignKey(
        OutletItem, on_delete=models.CASCADE, related_name="recipe_lines")
    inventory_item = models.ForeignKey(
        OutletInventoryItem, on_delete=models.PROTECT, related_name="used_in_recipes")
    quantity_per_unit = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        unique_together = ("item", "inventory_item")

    def __str__(self):
        return f"{self.item.name} -> {self.inventory_item.name}"
