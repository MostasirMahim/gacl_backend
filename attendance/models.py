from django.db import models
from django.conf import settings
from django.utils import timezone
from member.models import Member
from member_financial_management.utils.managers import ActiveManager


class AttendanceBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------
# Staff profile: anchors staff attendance + per-staff guest toggle
# (admin enables/disables whether a staff member may bring guests)
# ---------------------------------------------------------------
class StaffProfile(AttendanceBaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="staff_profile")
    staff_ID = models.CharField(max_length=100, unique=True, db_index=True)
    designation = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    guest_allowed = models.BooleanField(
        default=False,
        help_text="Admin toggle: can this staff member register guests?")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.staff_ID} ({self.user.username})"


# ---------------------------------------------------------------
# RFID cards. Members/staff have permanent cards; guests get a
# temporary card assigned at entry and released on exit.
# ---------------------------------------------------------------
class RFIDCard(AttendanceBaseModel):
    CARD_TYPE_CHOICES = [
        ("member", "member"),
        ("staff", "staff"),
        ("guest_temporary", "guest_temporary"),
    ]
    card_uid = models.CharField(max_length=100, unique=True, db_index=True)
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES)
    is_assigned = models.BooleanField(default=False)

    # at most one of these is set depending on card_type
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="rfid_cards")
    staff = models.ForeignKey(
        StaffProfile, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="rfid_cards")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.card_uid} [{self.card_type}]"


# ---------------------------------------------------------------
# Guest: a temporary visitor brought in under a HOST. The host is
# either a member or (if guest_allowed) a staff member. A guest may
# actually be a family member -- captured via guest_relation.
# ---------------------------------------------------------------
class Guest(AttendanceBaseModel):
    HOST_TYPE_CHOICES = [
        ("member", "member"),
        ("staff", "staff"),
    ]
    RELATION_CHOICES = [
        ("guest", "guest"),
        ("family", "family"),
    ]
    # mandatory
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)

    guest_relation = models.CharField(
        max_length=10, choices=RELATION_CHOICES, default="guest",
        help_text="Distinguishes an outside guest from a family member")
    host_type = models.CharField(max_length=10, choices=HOST_TYPE_CHOICES,
                                 default="member")

    # host linkage (exactly one based on host_type)
    host_member = models.ForeignKey(
        Member, on_delete=models.PROTECT, blank=True, null=True, default=None,
        related_name="guests")
    host_staff = models.ForeignKey(
        StaffProfile, on_delete=models.PROTECT, blank=True, null=True, default=None,
        related_name="guests")

    # temporary RFID assigned for the visit
    temporary_card = models.ForeignKey(
        RFIDCard, on_delete=models.SET_NULL, blank=True, null=True, default=None,
        related_name="guest_assignments")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.name} ({self.guest_relation})"


# ---------------------------------------------------------------
# Attendance records. One unified model with a subject type so that
# member / staff / guest check-ins live together and report cleanly.
# ---------------------------------------------------------------
class AttendanceRecord(AttendanceBaseModel):
    SUBJECT_CHOICES = [
        ("member", "member"),
        ("staff", "staff"),
        ("guest", "guest"),
    ]
    subject_type = models.CharField(
        max_length=10, choices=SUBJECT_CHOICES, db_index=True)

    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, blank=True, null=True, default=None,
        related_name="attendance_records")
    staff = models.ForeignKey(
        StaffProfile, on_delete=models.PROTECT, blank=True, null=True, default=None,
        related_name="attendance_records")
    guest = models.ForeignKey(
        Guest, on_delete=models.PROTECT, blank=True, null=True, default=None,
        related_name="attendance_records")

    card = models.ForeignKey(
        RFIDCard, on_delete=models.SET_NULL, blank=True, null=True, default=None,
        related_name="attendance_records")

    check_in = models.DateTimeField(default=timezone.now, db_index=True)
    check_out = models.DateTimeField(blank=True, null=True, default=None)

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-check_in"]

    @property
    def is_checked_out(self):
        return self.check_out is not None

    def __str__(self):
        return f"{self.subject_type} @ {self.check_in:%Y-%m-%d %H:%M}"
