from rest_framework import serializers
from .models import (
    RestaurantCuisineCategory, RestaurantCategory, Restaurant, RestaurantItemCategory, 
    RestaurantItem, RestaurantItemMedia, RestaurantMenuSection
)
from member.models import Member
from promo_code_app.models import PromoCode
import pdb
import os
from member_financial_management.models import IncomeParticular, IncomeReceivingOption


class RestaurantCuisineCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantCuisineCategory
        fields = ["id", "name"]


class RestaurantCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantCategory
        fields = ["id", "name"]


class RestaurantSerializer(serializers.Serializer):
    STATUS_CHOICES = [
        ('open', 'open'),
        ('closed', 'closed'),
    ]
    name = serializers.CharField(max_length=300)
    description = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField(max_length=250)
    state = serializers.CharField(max_length=250)
    postal_code = serializers.CharField(max_length=250)
    phone = serializers.CharField(max_length=14)
    operating_hours = serializers.IntegerField()
    capacity = serializers.IntegerField()
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    opening_time = serializers.TimeField()
    closing_time = serializers.TimeField()
    booking_fees_per_seat = serializers.DecimalField(
        max_digits=10, decimal_places=2)
    cuisine_type = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantCuisineCategory.objects.all())
    restaurant_type = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantCategory.objects.all())

    # Dynamic layout and banner fields
    slug = serializers.SlugField(required=False, allow_null=True)
    banner_bg_image = serializers.ImageField(required=False, allow_null=True)
    banner_title = serializers.CharField(required=False, allow_blank=True, default="")
    banner_description = serializers.CharField(required=False, allow_blank=True, default="")
    about_text = serializers.CharField(required=False, allow_blank=True, default="")
    meta_title = serializers.CharField(required=False, allow_blank=True, default="")
    meta_description = serializers.CharField(required=False, allow_blank=True, default="")
    delivery_banner_title = serializers.CharField(required=False, allow_blank=True, default="30 Minutes Delivery!")
    delivery_banner_text = serializers.CharField(required=False, allow_blank=True, default="")
    reservation_banner_title = serializers.CharField(required=False, allow_blank=True, default="Reservation Your Favorite Private Table")
    reservation_banner_text = serializers.CharField(required=False, allow_blank=True, default="")
    reservation_banner_launch_menu = serializers.CharField(required=False, allow_blank=True, default="30+ items")
    reservation_banner_dinner_menu = serializers.CharField(required=False, allow_blank=True, default="50+ items")

    def validate_name(self, value):
        if Restaurant.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                f"Restaurant with name {value} already exists")
        return value

    def create(self, validated_data):
        instance = Restaurant.objects.create(**validated_data)
        return instance


class RestaurantViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = "__all__"
        depth = 1


class RestaurantUpdateSerializer(serializers.ModelSerializer):
    """Used for PATCH/PUT update of a single restaurant (Bug 4.1)."""
    class Meta:
        model = Restaurant
        exclude = ["is_active", "created_at", "updated_at"]
        extra_kwargs = {f: {"required": False} for f in [
            "name", "description", "address", "city", "state", "postal_code",
            "phone", "operating_hours", "capacity", "status", "opening_time",
            "closing_time", "booking_fees_per_seat", "cuisine_type",
            "restaurant_type", "slug", "banner_bg_image", "banner_title",
            "banner_description", "about_text", "meta_title", "meta_description",
            "delivery_banner_title", "delivery_banner_text", "reservation_banner_title",
            "reservation_banner_text", "reservation_banner_launch_menu", "reservation_banner_dinner_menu", "footer_config"]}

    def validate_name(self, value):
        qs = Restaurant.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError(
                f"Restaurant with name {value} already exists")
        return value


class RestaurantItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantItemCategory
        fields = "__all__"


class RestaurantItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=300)
    description = serializers.CharField(max_length=300)
    availability = serializers.BooleanField()
    unit = serializers.CharField(max_length=100)
    unit_cost = serializers.DecimalField(max_digits=6, decimal_places=2)
    selling_price = serializers.DecimalField(max_digits=6, decimal_places=2)
    category = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantItemCategory.objects.filter(is_active=True))
    restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.filter(is_active=True))

    # Additional fields to support front-end layout
    slug = serializers.SlugField(required=False, allow_null=True)
    sku = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    stock = serializers.IntegerField(required=False, default=0)
    half_price = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=2)
    free_bonus = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sub_items = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.JSONField(required=False, default=list)
    additional_info = serializers.JSONField(required=False, default=dict)
    menu_section = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantMenuSection.objects.filter(is_active=True), required=False, allow_null=True, default=None)
    cover_image = serializers.ImageField(required=False, allow_null=True)

    def validate_name(self, value):
        if RestaurantItem.objects.filter(name=value).exists():
            raise serializers.ValidationError(f"{value} already exists")
        return value

    def create(self, validated_data):
        instance = RestaurantItem.objects.create(**validated_data)
        return instance


class ItemMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantItemMedia
        fields = ['id', 'image']


class RestaurantItemForViewSerializer(serializers.ModelSerializer):
    restaurant = serializers.CharField()
    category = serializers.CharField()
    category_id = serializers.ReadOnlyField(source="category.id")
    menu_section_id = serializers.ReadOnlyField(source="menu_section.id")
    item_media = ItemMediaSerializer(many=True, read_only=True)

    class Meta:
        model = RestaurantItem
        fields = "__all__"
        depth = 1


class RestaurantItemUpdateSerializer(serializers.ModelSerializer):
    """PATCH update for a single restaurant item (Bug 4.2)."""
    class Meta:
        model = RestaurantItem
        exclude = ["is_active", "created_at", "updated_at"]
        extra_kwargs = {"restaurant": {"required": False},
                        "category": {"required": False},
                        "name": {"required": False},
                        "menu_section": {"required": False},
                        "cover_image": {"required": False}}



class RestaurantItemMediaSerializer(serializers.Serializer):
    image = serializers.ImageField()
    item = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantItem.objects.all())

    def create(self, validated_data):
        instance = RestaurantItemMedia.objects.create(**validated_data)
        return instance


class RestaurantItemMediaForViewSerializer(serializers.Serializer):
    image = serializers.ImageField()


class RestaurantSingleItemForBuySerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantItem.objects.filter(is_active=True))
    quantity = serializers.IntegerField()


class RestaurantItemBuySerializer(serializers.Serializer):
    restaurant_items = serializers.ListSerializer(
        child=RestaurantSingleItemForBuySerializer(), allow_empty=False)
    member_ID = serializers.CharField()
    restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.filter(is_active=True))
    promo_code = serializers.CharField(required=False, default=None)

    def validate_member_ID(self, value):
        if not Member.objects.filter(member_ID=value).exists():
            raise serializers.ValidationError(f"{value} is not a member")
        return value

    def validate_promo_code(self, value):
        if value == None:
            return value
        try:
            promo_code = PromoCode.objects.get(promo_code=value)
            is_in_restaurant_category = promo_code.category.filter(
                name__iexact="restaurant").exists()
            if not promo_code.is_promo_code_valid():
                raise serializers.ValidationError(
                    "This promo code is expired or not valid any more.")
            else:
                if is_in_restaurant_category:
                    return promo_code
                else:
                    raise serializers.ValidationError(
                        "This is not a restaurant category promo code.")
        except PromoCode.DoesNotExist as e:
            raise serializers.ValidationError(
                "This is not a valid promo code.")


class RestaurantExcelUpload(serializers.Serializer):
    excel_file = serializers.FileField()
    restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.active_objects.all())
    income_particular = serializers.PrimaryKeyRelatedField(
        queryset=IncomeParticular.active_objects.all())
    received_from = serializers.PrimaryKeyRelatedField(
        queryset=IncomeReceivingOption.active_objects.all())

    def validate_excel_file(self, value):
        # Check file extension
        valid_extensions = ['.xls', '.xlsx']

        ext = os.path.splitext(value.name)[1]  # Get the file extension
        if ext.lower() not in valid_extensions:
            raise serializers.ValidationError(
                "Only .xls and .xlsx files are allowed.")
        return value


# ============================================================
# ORDERING / SPICY / INVENTORY SERIALIZERS
# ============================================================
from .models import (
    SpicyLevel, RestaurantItemSetting, RestaurantOrder, RestaurantOrderItem,
    RestaurantInventoryItem, RestaurantInventoryTransaction, RestaurantItemRecipe,
)


class SpicyLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpicyLevel
        fields = ["id", "name", "rank", "is_active"]


class RestaurantItemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantItemSetting
        fields = ["id", "item", "spicy_selectable", "is_public_show"]


class OrderItemInputSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    spicy_level_id = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class CreateOrderSerializer(serializers.Serializer):
    restaurant_id = serializers.IntegerField()
    member_id = serializers.IntegerField(required=False, allow_null=True)
    guest_id = serializers.IntegerField(required=False, allow_null=True)
    serve_location = serializers.ChoiceField(
        choices=["restaurant", "room"], default="restaurant")
    room_number = serializers.CharField(required=False, allow_blank=True, default="")
    placed_by = serializers.ChoiceField(
        choices=["member", "waiter"], default="member")
    note = serializers.CharField(required=False, allow_blank=True, default="")
    require_otp = serializers.BooleanField(default=True)
    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value


class VerifyOtpSerializer(serializers.Serializer):
    otp_code = serializers.CharField(max_length=6)


class KitchenStatusSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(
        choices=["preparing", "ready", "served", "cancelled"])


class BillOrderSerializer(serializers.Serializer):
    payment_mode = serializers.ChoiceField(
        choices=["pos", "sslcommerz", "cash", "due"])
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)


class RestaurantOrderItemViewSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    spicy_level_name = serializers.CharField(
        source="spicy_level.name", read_only=True, default=None)

    class Meta:
        model = RestaurantOrderItem
        fields = ["id", "item", "item_name", "quantity", "unit_price",
                  "spicy_level", "spicy_level_name", "note"]


class RestaurantOrderViewSerializer(serializers.ModelSerializer):
    items = RestaurantOrderItemViewSerializer(many=True, read_only=True)

    class Meta:
        model = RestaurantOrder
        fields = ["id", "order_number", "status", "serve_location",
                  "room_number", "placed_by", "sub_total", "total_amount",
                  "note", "otp_verified", "restaurant", "member", "guest",
                  "waiter", "invoice", "items", "created_at"]


class RestaurantInventoryItemSerializer(serializers.ModelSerializer):
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = RestaurantInventoryItem
        fields = ["id", "name", "unit", "current_quantity", "reorder_level",
                  "unit_cost", "restaurant", "is_low", "is_active"]


class RestaurantInventoryTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantInventoryTransaction
        fields = ["id", "inventory_item", "movement", "quantity", "reason",
                  "order", "created_by", "created_at"]
        read_only_fields = ["created_by"]


class RestaurantItemRecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantItemRecipe
        fields = ["id", "item", "inventory_item", "quantity_per_unit"]
