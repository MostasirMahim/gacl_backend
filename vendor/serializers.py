from rest_framework import serializers
from .models import (
    Vendor, VendorServiceCategory, VendorServiceOffer, VendorPayment,
)


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "contact_person", "phone", "email",
                  "address", "note", "is_active"]


class VendorServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorServiceCategory
        fields = ["id", "name", "description", "is_active"]


class VendorServiceOfferSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = VendorServiceOffer
        fields = ["id", "vendor", "vendor_name", "category", "category_name",
                  "title", "description", "price", "billing_cycle", "status",
                  "is_active"]


class VendorPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorPayment
        fields = ["id", "offer", "amount", "paid_on", "note", "created_by"]
        read_only_fields = ["created_by", "paid_on"]


class VendorPaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, default="")
