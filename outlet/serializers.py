from rest_framework import serializers
from .models import (
    Outlet, OutletItemCategory, OutletItem, OutletItemMedia, CrossOrderingRule,
    OutletOrder, OutletOrderItem, OutletInventoryItem, OutletInventoryTransaction,
    OutletItemRecipe,
)


class OutletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = ["id", "name", "outlet_type", "description", "address", "phone",
                  "capacity", "status", "opening_time", "closing_time", "admin",
                  "is_active"]


class OutletItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OutletItemCategory
        fields = ["id", "name", "outlet_type", "is_active"]


class OutletItemMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutletItemMedia
        fields = ["id", "image", "item"]


class OutletItemSerializer(serializers.ModelSerializer):
    media = OutletItemMediaSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source="category.name",
                                          read_only=True, default=None)
    outlet_name = serializers.CharField(source="outlet.name",
                                        read_only=True, default=None)

    class Meta:
        model = OutletItem
        fields = ["id", "name", "description", "unit", "unit_cost",
                  "selling_price", "availability", "spicy_selectable",
                  "is_public_show", "category", "category_name", "outlet",
                  "outlet_name", "media", "is_active"]


class CrossOrderingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrossOrderingRule
        fields = ["id", "source_type", "target_type", "allowed",
                  "requires_room_number", "is_active"]


class OutletOrderItemInputSerializer(serializers.Serializer):
    source = serializers.CharField(required=False, allow_blank=True, default="")
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    spicy_level_id = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class CreateOutletOrderSerializer(serializers.Serializer):
    outlet_id = serializers.IntegerField()
    member_id = serializers.IntegerField()
    guest_id = serializers.IntegerField(required=False, allow_null=True)
    placed_by = serializers.ChoiceField(choices=["member", "waiter"], default="member")
    room_number = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")
    require_otp = serializers.BooleanField(default=True)
    items = OutletOrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value


class VerifyOtpSerializer(serializers.Serializer):
    otp_code = serializers.CharField(max_length=6)


class StatusSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(
        choices=["preparing", "ready", "served", "cancelled"])


class BillOutletOrderSerializer(serializers.Serializer):
    payment_mode = serializers.ChoiceField(choices=["pos", "sslcommerz", "cash", "due"])
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)


class OutletOrderItemViewSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(read_only=True)
    spicy_level_name = serializers.CharField(
        source="spicy_level.name", read_only=True, default=None)

    class Meta:
        model = OutletOrderItem
        fields = ["id", "outlet_item", "restaurant_item", "item_name", "quantity",
                  "unit_price", "spicy_level", "spicy_level_name", "note", "source_type"]


class OutletOrderViewSerializer(serializers.ModelSerializer):
    items = OutletOrderItemViewSerializer(many=True, read_only=True)

    class Meta:
        model = OutletOrder
        fields = ["id", "order_number", "status", "placed_by", "outlet",
                  "room_number", "sub_total", "total_amount", "note",
                  "otp_verified", "member", "guest", "waiter", "invoice",
                  "items", "created_at"]


class OutletInventoryItemSerializer(serializers.ModelSerializer):
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = OutletInventoryItem
        fields = ["id", "name", "unit", "current_quantity", "reorder_level",
                  "unit_cost", "outlet", "is_low", "is_active"]


class OutletInventoryTransactionSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(
        source="inventory_item.name", read_only=True, default=None)

    class Meta:
        model = OutletInventoryTransaction
        fields = ["id", "inventory_item", "inventory_item_name", "movement",
                  "quantity", "reason", "order", "created_by", "created_at"]
        read_only_fields = ["created_by"]


class OutletItemRecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutletItemRecipe
        fields = ["id", "item", "inventory_item", "quantity_per_unit"]
