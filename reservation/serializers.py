from rest_framework import serializers
from .models import ReservableResource, Reservation


class ReservableResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservableResource
        fields = ["id", "name", "resource_type", "description", "advance_amount",
                  "capacity", "max_per_member", "slot_minutes", "opening_time",
                  "closing_time", "status", "is_active"]


class CreateReservationSerializer(serializers.Serializer):
    resource_id = serializers.IntegerField()
    member_id = serializers.IntegerField(required=False, allow_null=True)
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    party_size = serializers.IntegerField(min_value=1, default=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class PayAdvanceSerializer(serializers.Serializer):
    payment_mode = serializers.ChoiceField(choices=["pos", "sslcommerz", "cash"])


class ReservationViewSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source="resource.name", read_only=True)
    resource_type = serializers.CharField(source="resource.resource_type", read_only=True)
    member_ID = serializers.CharField(source="member.member_ID", read_only=True, default=None)
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = ["id", "reservation_number", "status", "resource",
                  "resource_name", "resource_type", "member", "member_ID",
                  "member_name", "start_time", "end_time", "party_size",
                  "advance_amount", "advance_paid", "note", "invoice",
                  "created_at"]

    def get_member_name(self, obj):
        if obj.member:
            return f"{obj.member.first_name} {obj.member.last_name}".strip()
        return None


class AvailabilityQuerySerializer(serializers.Serializer):
    resource_id = serializers.IntegerField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
