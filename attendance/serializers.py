from rest_framework import serializers
from .models import StaffProfile, RFIDCard, Guest, AttendanceRecord


class StaffProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = ["id", "user", "username", "full_name", "staff_ID",
                  "designation", "phone", "guest_allowed", "is_active"]

    def get_full_name(self, obj):
        if obj.user:
            name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            return name or obj.user.username
        return ""


class StaffGuestToggleSerializer(serializers.Serializer):
    guest_allowed = serializers.BooleanField()


class RFIDCardSerializer(serializers.ModelSerializer):
    # human-friendly display info for listing / history
    member_ID = serializers.CharField(source="member.member_ID",
                                       read_only=True, default=None)
    member_name = serializers.SerializerMethodField()
    staff_ID = serializers.CharField(source="staff.staff_ID",
                                     read_only=True, default=None)
    staff_name = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()

    class Meta:
        model = RFIDCard
        fields = ["id", "card_uid", "card_type", "is_assigned",
                  "member", "member_ID", "member_name",
                  "staff", "staff_ID", "staff_name",
                  "assigned_to", "is_active", "created_at"]

    def get_member_name(self, obj):
        if obj.member:
            return f"{obj.member.first_name} {obj.member.last_name}".strip()
        return None

    def get_staff_name(self, obj):
        if obj.staff and obj.staff.user:
            n = f"{obj.staff.user.first_name} {obj.staff.user.last_name}".strip()
            return n or obj.staff.user.username
        return None

    def get_assigned_to(self, obj):
        if obj.card_type == "member" and obj.member:
            return f"{obj.member.member_ID} - {obj.member.first_name} {obj.member.last_name}".strip()
        if obj.card_type == "staff" and obj.staff:
            nm = ""
            if obj.staff.user:
                nm = f"{obj.staff.user.first_name} {obj.staff.user.last_name}".strip()
            return f"{obj.staff.staff_ID} - {nm}".strip(" -")
        if obj.card_type == "guest_temporary":
            return "Guest (temporary)"
        return "Unassigned"

    def validate(self, attrs):
        card_type = attrs.get("card_type")
        member = attrs.get("member")
        staff = attrs.get("staff")
        if card_type == "member" and member:
            attrs["is_assigned"] = True
        if card_type == "staff" and staff:
            attrs["is_assigned"] = True
        return attrs


class RFIDCardAssignSerializer(serializers.Serializer):
    """Assign (or reassign) a card to a member or staff."""
    card_type = serializers.ChoiceField(
        choices=["member", "staff", "guest_temporary"])
    member = serializers.IntegerField(required=False, allow_null=True)
    staff = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        ct = attrs.get("card_type")
        if ct == "member" and not attrs.get("member"):
            raise serializers.ValidationError(
                {"member": "Member is required for a member card."})
        if ct == "staff" and not attrs.get("staff"):
            raise serializers.ValidationError(
                {"staff": "Staff is required for a staff card."})
        return attrs


class GuestSerializer(serializers.ModelSerializer):
    host_name = serializers.SerializerMethodField()
    temporary_card_uid = serializers.CharField(
        source="temporary_card.card_uid", read_only=True, default=None)

    class Meta:
        model = Guest
        fields = ["id", "name", "phone", "guest_relation", "host_type",
                  "host_member", "host_staff", "host_name",
                  "temporary_card", "temporary_card_uid", "is_active",
                  "created_at"]

    def get_host_name(self, obj):
        if obj.host_type == "member" and obj.host_member:
            return f"{obj.host_member.member_ID} - {obj.host_member.first_name}".strip()
        if obj.host_type == "staff" and obj.host_staff:
            if obj.host_staff.user:
                return f"{obj.host_staff.staff_ID} - {obj.host_staff.user.first_name}".strip()
            return obj.host_staff.staff_ID
        return None

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
    # rich display fields so the record table shows who attended
    subject_name = serializers.SerializerMethodField()
    subject_identifier = serializers.SerializerMethodField()
    card_uid = serializers.CharField(source="card.card_uid",
                                     read_only=True, default=None)

    class Meta:
        model = AttendanceRecord
        fields = ["id", "subject_type", "subject_name", "subject_identifier",
                  "member", "staff", "guest", "card", "card_uid",
                  "check_in", "check_out", "is_active"]
        read_only_fields = ["check_in"]

    def get_subject_name(self, obj):
        if obj.subject_type == "member" and obj.member:
            return f"{obj.member.first_name} {obj.member.last_name}".strip()
        if obj.subject_type == "staff" and obj.staff:
            if obj.staff.user:
                n = f"{obj.staff.user.first_name} {obj.staff.user.last_name}".strip()
                return n or obj.staff.user.username
            return obj.staff.staff_ID
        if obj.subject_type == "guest" and obj.guest:
            return obj.guest.name
        return ""

    def get_subject_identifier(self, obj):
        if obj.subject_type == "member" and obj.member:
            return obj.member.member_ID
        if obj.subject_type == "staff" and obj.staff:
            return obj.staff.staff_ID
        if obj.subject_type == "guest" and obj.guest:
            return obj.guest.phone
        return ""


class CheckInByCardSerializer(serializers.Serializer):
    """Check in/out by scanning an RFID card UID."""
    card_uid = serializers.CharField(max_length=100)
