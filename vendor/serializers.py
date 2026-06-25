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
    last_payment_date = serializers.SerializerMethodField()
    is_paid_current_period = serializers.SerializerMethodField()

    class Meta:
        model = VendorServiceOffer
        fields = ["id", "vendor", "vendor_name", "category", "category_name",
                  "title", "description", "price", "billing_cycle", "status",
                  "last_payment_date", "is_paid_current_period", "is_active"]

    def get_last_payment_date(self, obj):
        last = obj.payments.order_by("-paid_on", "-id").first()
        return last.paid_on if last else None

    def get_is_paid_current_period(self, obj):
        """For monthly offers, whether the current month is already paid
        (Bug 8.1 — hide the pay button after paying the current bill)."""
        from django.utils import timezone
        if obj.billing_cycle != "monthly":
            # one-time/yearly: paid if any payment exists
            return obj.payments.exists()
        now = timezone.localdate()
        return obj.payments.filter(
            period_month=now.month, period_year=now.year).exists() or \
            obj.payments.filter(
                paid_on__month=now.month, paid_on__year=now.year).exists()


class VendorPaymentSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(
        source="offer.vendor.name", read_only=True)
    category_name = serializers.CharField(
        source="offer.category.name", read_only=True)
    offer_title = serializers.CharField(source="offer.title", read_only=True)

    class Meta:
        model = VendorPayment
        fields = ["id", "offer", "offer_title", "vendor_name", "category_name",
                  "amount", "paid_on", "reference", "payment_type",
                  "period_month", "period_year", "note", "created_by"]
        read_only_fields = ["created_by"]


class VendorPaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    payment_type = serializers.ChoiceField(
        choices=["one_time", "monthly", "yearly"], required=False,
        default="one_time")
    period_month = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=12)
    period_year = serializers.IntegerField(
        required=False, allow_null=True, min_value=2000, max_value=2100)
    paid_on = serializers.DateField(required=False, allow_null=True)
