from rest_framework import serializers
from .models import ExpenseCategory, Expense


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_active"]


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Expense
        fields = ["id", "source_module", "category", "category_name", "amount",
                  "description", "incurred_on", "reference_type", "reference_id",
                  "created_by"]
        read_only_fields = ["created_by", "incurred_on"]


class ExpenseInputSerializer(serializers.Serializer):
    category_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    source_module = serializers.CharField(required=False, default="manual")
