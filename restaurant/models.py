from django.db import models
from member_financial_management.utils.managers import ActiveManager


class RestaurantBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class RestaurantCuisineCategory(RestaurantBaseModel):
    name = models.CharField(max_length=300, unique=True)

    def __str__(self):
        return self.name


class RestaurantCategory(RestaurantBaseModel):
    name = models.CharField(max_length=300, unique=True)

    def __str__(self):
        return self.name


class Restaurant(RestaurantBaseModel):
    STATUS_CHOICES = [
        ('open', 'open'),
        ('closed', 'closed'),
    ]
    name = models.CharField(max_length=300, unique=True)
    description = models.TextField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=250, blank=True, default="")
    state = models.CharField(max_length=250, blank=True, default="")
    postal_code = models.CharField(max_length=250, blank=True, default="")
    phone = models.CharField(max_length=14, blank=True, default="")
    operating_hours = models.IntegerField(default=12)
    capacity = models.IntegerField(default=50)
    status = models.CharField(
        max_length=6, choices=STATUS_CHOICES, default="open")
    opening_time = models.TimeField(blank=True, null=True, default=None)
    closing_time = models.TimeField(blank=True, null=True, default=None)
    booking_fees_per_seat = models.DecimalField(
        blank=True, null=True, default=None, decimal_places=2, max_digits=10)

    # relations
    cuisine_type = models.ForeignKey(
        RestaurantCuisineCategory, on_delete=models.PROTECT, related_name="restaurant_cuisine")
    restaurant_type = models.ForeignKey(
        RestaurantCategory, on_delete=models.PROTECT, related_name="restaurant_category")

    # Dynamic layout and banner fields
    slug = models.SlugField(max_length=350, unique=True, blank=True, null=True)
    banner_bg_image = models.ImageField(upload_to="restaurant/banners/", blank=True, null=True)
    banner_title = models.CharField(max_length=300, blank=True, default="")
    banner_description = models.TextField(blank=True, default="")
    about_text = models.TextField(blank=True, default="")
    meta_title = models.CharField(max_length=300, blank=True, default="")
    meta_description = models.TextField(blank=True, default="")
    delivery_banner_title = models.CharField(max_length=200, default="30 Minutes Delivery!")
    delivery_banner_text = models.TextField(blank=True, default="")
    reservation_banner_title = models.CharField(max_length=200, default="Reservation Your Favorite Private Table")
    reservation_banner_text = models.TextField(blank=True, default="")
    reservation_banner_launch_menu = models.CharField(max_length=100, default="30+ items")
    reservation_banner_dinner_menu = models.CharField(max_length=100, default="50+ items")
    footer_config = models.JSONField(default=dict, blank=True)

    # managers
    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return self.name


class RestaurantItemCategory(RestaurantBaseModel):
    name = models.CharField(max_length=300, unique=True)

    def __str__(self):
        return self.name


class RestaurantMenuSection(RestaurantBaseModel):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="menu_sections")
    title = models.CharField(max_length=300)
    cover_image = models.ImageField(upload_to="restaurant/sections/", blank=True, null=True)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    layout_type = models.CharField(max_length=50, choices=[('default', 'Default/Tabs'), ('left', 'Left Column'), ('right', 'Right Column')], default='default')

    class Meta:
        ordering = ["order"]
        unique_together = ("restaurant", "title")

    def __str__(self):
        return f"{self.restaurant.name} - {self.title}"


class RestaurantItem(RestaurantBaseModel):
    name = models.CharField(max_length=300, unique=True)
    description = models.TextField(blank=True, default="")
    availability = models.BooleanField(default=True, db_index=True)
    unit = models.CharField(max_length=100)
    unit_cost = models.DecimalField(max_digits=6, decimal_places=2)
    selling_price = models.DecimalField(max_digits=6, decimal_places=2)
    cover_image = models.ImageField(upload_to="restaurant/items/covers/", null=True, blank=True)

    # relations
    category = models.ForeignKey(
        RestaurantItemCategory, on_delete=models.PROTECT, related_name="item_category")
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.PROTECT, related_name="restaurant_item_restaurant")

    # Additional fields to support front-end layout
    slug = models.SlugField(max_length=350, unique=True, blank=True, null=True)
    sku = models.CharField(max_length=100, blank=True, null=True)
    stock = models.IntegerField(default=0)
    half_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    free_bonus = models.CharField(max_length=250, blank=True, null=True, default="")
    sub_items = models.CharField(max_length=500, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    additional_info = models.JSONField(default=dict, blank=True)
    menu_section = models.ForeignKey(
        RestaurantMenuSection, on_delete=models.SET_NULL, null=True, blank=True, related_name="items")

    def __str__(self):
        return self.name


class RestaurantItemMedia(RestaurantBaseModel):
    image = models.ImageField(upload_to="restaurant/items/")
    item = models.ForeignKey(
        RestaurantItem, on_delete=models.CASCADE, related_name="item_media")

    def __str__(self):
        return self.item.name


class RestaurantTestimonial(RestaurantBaseModel):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="testimonials")
    name = models.CharField(max_length=300)
    designation = models.CharField(max_length=200, blank=True, default="")
    rating = models.PositiveSmallIntegerField(default=5)
    title = models.CharField(max_length=300, blank=True, default="")
    text = models.TextField()

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"


class RestaurantItemReview(RestaurantBaseModel):
    item = models.ForeignKey(
        RestaurantItem, on_delete=models.CASCADE, related_name="reviews")
    member = models.ForeignKey(
        "member.Member", on_delete=models.SET_NULL, null=True, blank=True, related_name="restaurant_item_reviews")
    reviewer_name = models.CharField(max_length=200, blank=True, default="Admin")
    reviewer_avatar = models.ImageField(upload_to="restaurant/reviews/", blank=True, null=True)
    rating = models.PositiveSmallIntegerField(default=5)
    review_text = models.TextField()

    def __str__(self):
        name = self.member.user.username if self.member else self.reviewer_name
        return f"{self.item.name} - {name} ({self.rating} stars)"


# ============================================================
# ORDERING + KITCHEN FLOW + INVENTORY (added for club management)
# ============================================================
from django.conf import settings
from django.utils import timezone


class SpicyLevel(RestaurantBaseModel):
    """Selectable spice levels e.g. Mild / Medium / Hot / Extra Hot."""
    name = models.CharField(max_length=100, unique=True)
    rank = models.PositiveSmallIntegerField(
        default=0, help_text="Lower = milder, used for ordering in UI")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return self.name


# Extend RestaurantItem capabilities without touching the original class body.
# An item may disable spicy selection (restaurant admin choice at menu-post time)
# and may be flagged for public (show) menu visibility.
class RestaurantItemSetting(RestaurantBaseModel):
    item = models.OneToOneField(
        RestaurantItem, on_delete=models.CASCADE, related_name="setting")
    spicy_selectable = models.BooleanField(
        default=False,
        help_text="If False, members cannot pick a spicy level for this item")
    is_public_show = models.BooleanField(
        default=False,
        help_text="If True, appears on the public 'show' menu the admin posts")

    def __str__(self):
        return f"settings::{self.item.name}"


class RestaurantOrder(RestaurantBaseModel):
    """A member (or guest under a member, or waiter-on-behalf) order."""
    ORDER_STATUS_CHOICES = [
        ("pending_otp", "pending_otp"),     # created, waiting OTP confirm
        ("confirmed", "confirmed"),         # OTP confirmed -> goes to kitchen
        ("preparing", "preparing"),         # kitchen accepted / cooking
        ("ready", "ready"),                 # cooked, ready to serve
        ("served", "served"),               # delivered to room/table
        ("billed", "billed"),               # invoice generated
        ("cancelled", "cancelled"),
    ]
    SERVE_LOCATION_CHOICES = [
        ("room", "room"),           # deliver to a room number
        ("restaurant", "restaurant"),  # serve in the restaurant itself
    ]
    PLACED_BY_CHOICES = [
        ("member", "member"),       # member from own phone
        ("waiter", "waiter"),       # waiter on behalf of member/guest
    ]

    order_number = models.CharField(max_length=60, unique=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=ORDER_STATUS_CHOICES, default="pending_otp", db_index=True)
    serve_location = models.CharField(
        max_length=15, choices=SERVE_LOCATION_CHOICES, default="restaurant")
    room_number = models.CharField(max_length=30, blank=True, default="")
    placed_by = models.CharField(
        max_length=15, choices=PLACED_BY_CHOICES, default="member")

    sub_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")

    # OTP confirmation
    otp_code = models.CharField(max_length=6, blank=True, default="")
    otp_verified = models.BooleanField(default=False)
    otp_sent_at = models.DateTimeField(blank=True, null=True, default=None)
    confirmed_at = models.DateTimeField(blank=True, null=True, default=None)

    # relations
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.PROTECT, related_name="orders")
    # The member the order is billed to (guest/family orders bill the host member)
    member = models.ForeignKey(
        "member.Member", on_delete=models.PROTECT, related_name="restaurant_orders")
    # If the order is for a guest/family member rather than the member directly
    guest = models.ForeignKey(
        "attendance.Guest", on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="restaurant_orders")
    waiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="waiter_orders")
    # linked invoice once billed
    invoice = models.ForeignKey(
        "member_financial_management.Invoice", on_delete=models.SET_NULL,
        blank=True, null=True, default=None, related_name="restaurant_orders")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number


class RestaurantOrderItem(RestaurantBaseModel):
    order = models.ForeignKey(
        RestaurantOrder, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(
        RestaurantItem, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    spicy_level = models.ForeignKey(
        SpicyLevel, on_delete=models.SET_NULL, blank=True, null=True, default=None,
        related_name="order_items")
    note = models.CharField(max_length=300, blank=True, default="")

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.item.name} x{self.quantity}"


# ---------------- Inventory ----------------
class RestaurantInventoryItem(RestaurantBaseModel):
    """Stock-tracked raw products / consumables for a restaurant."""
    name = models.CharField(max_length=300)
    unit = models.CharField(max_length=50, help_text="e.g. kg, ltr, pcs")
    current_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Alert when stock falls to/below this")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.PROTECT, related_name="inventory_items")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        unique_together = ("name", "restaurant")

    @property
    def is_low(self):
        return self.current_quantity <= self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"


class RestaurantInventoryTransaction(RestaurantBaseModel):
    """Every stock movement: purchase (in) or consumption/wastage (out)."""
    MOVEMENT_CHOICES = [
        ("in", "in"),
        ("out", "out"),
    ]
    inventory_item = models.ForeignKey(
        RestaurantInventoryItem, on_delete=models.PROTECT, related_name="movements")
    movement = models.CharField(max_length=3, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=255, blank=True, default="")
    # optional link to the order that consumed the stock
    order = models.ForeignKey(
        RestaurantOrder, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="inventory_movements")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="inventory_movements")

    def __str__(self):
        return f"{self.movement} {self.quantity} {self.inventory_item.name}"


# Recipe mapping: how much inventory a menu item consumes (optional, enables auto-deduct)
class RestaurantItemRecipe(RestaurantBaseModel):
    item = models.ForeignKey(
        RestaurantItem, on_delete=models.CASCADE, related_name="recipe_lines")
    inventory_item = models.ForeignKey(
        RestaurantInventoryItem, on_delete=models.PROTECT, related_name="used_in_recipes")
    quantity_per_unit = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Inventory consumed per 1 unit of the menu item")

    class Meta:
        unique_together = ("item", "inventory_item")

    def __str__(self):
        return f"{self.item.name} -> {self.inventory_item.name}"
