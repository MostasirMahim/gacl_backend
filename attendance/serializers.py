from rest_framework import serializers
from .models import StaffProfile, RFIDCard, Guest, AttendanceRecord


class StaffProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = StaffProfile
        fields = ["id", "user", "username", "staff_ID", "designation",
                  "phone", "guest_allowed", "is_active"]


class StaffGuestToggleSerializer(serializers.Serializer):
    guest_allowed = serializers.BooleanField()


class RFIDCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFIDCard
        fields = ["id", "card_uid", "card_type", "is_assigned",
                  "member", "staff", "is_active"]


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ["id", "name", "phone", "guest_relation", "host_type",
                  "host_member", "host_staff", "temporary_card", "is_active"]

    def validate(self, attrs):
        host_type = attrs.get("host_type", "member")
        if host_type == "member" and not attrs.get("host_member"):
            raise serializers.ValidationError(
                {"host_member": "Required when host_type is 'member'."})
        if host_type == "staff":
            host_staff = attrs.get("host_staff")
            if not host_staff:
                raise serializers.ValidationError(
                    {"host_staff": "Required when host_type is 'staff'."})
            if not host_staff.guest_allowed:
                raise serializers.ValidationError(
                    {"host_staff": "This staff member is not allowed to register guests."})
        if not attrs.get("name"):
            raise serializers.ValidationError({"name": "Name is mandatory."})
        if not attrs.get("phone"):
            raise serializers.ValidationError({"phone": "Phone is mandatory."})
        return attrs


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = ["id", "subject_type", "member", "staff", "guest", "card",
                  "check_in", "check_out", "is_active"]
        read_only_fields = ["check_in"]


class CheckInByCardSerializer(serializers.Serializer):
    """Check in/out by scanning an RFID card UID."""
    card_uid = serializers.CharField(max_length=100)
