from django.db import models
from django.conf import settings
from member_financial_management.utils.managers import ActiveManager


class ReservationBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# ============================================================
# A bookable resource: card room, pool, badminton court, paddle court.
# Admin sets the advance amount, the max number of concurrent reservations
# (capacity), and the highest number of slots a single member may hold.
# ============================================================
class ReservableResource(ReservationBaseModel):
    RESOURCE_TYPE_CHOICES = [
        ("card_room", "card_room"),
        ("pool", "pool"),
        ("badminton", "badminton"),
        ("paddle", "paddle"),
    ]
    name = models.CharField(max_length=200, unique=True)
    resource_type = models.CharField(
        max_length=20, choices=RESOURCE_TYPE_CHOICES, db_index=True)
    description = models.TextField(blank=True, default="")

    # advance payment the member pays to reserve (admin-set)
    advance_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Advance payment required to confirm a reservation")
    # how many reservations can run at the same time (concurrent capacity)
    capacity = models.PositiveIntegerField(
        default=1, help_text="Max concurrent reservations for this resource")
    # the highest number of active/future reservations a single member may hold
    max_per_member = models.PositiveIntegerField(
        default=1, help_text="Highest number of simultaneous bookings per member")
    # slot length in minutes (used to validate/normalise bookings)
    slot_minutes = models.PositiveIntegerField(default=60)

    opening_time = models.TimeField(blank=True, null=True, default=None)
    closing_time = models.TimeField(blank=True, null=True, default=None)
    status = models.CharField(
        max_length=20,
        choices=[("open", "open"), ("closed", "closed"), ("maintenance", "maintenance")],
        default="open")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.name} ({self.resource_type})"


class Reservation(ReservationBaseModel):
    STATUS_CHOICES = [
        ("pending_payment", "pending_payment"),  # created, advance not yet paid
        ("confirmed", "confirmed"),              # advance paid, slot held
        ("cancelled", "cancelled"),
        ("completed", "completed"),
    ]
    reservation_number = models.CharField(max_length=60, unique=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending_payment", db_index=True)

    resource = models.ForeignKey(
        ReservableResource, on_delete=models.PROTECT, related_name="reservations")
    member = models.ForeignKey(
        "member.Member", on_delete=models.PROTECT, related_name="reservations")

    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    party_size = models.PositiveIntegerField(default=1)

    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_paid = models.BooleanField(default=False)
    note = models.TextField(blank=True, default="")

    # link to the financial records once the advance is paid
    invoice = models.ForeignKey(
        "member_financial_management.Invoice", on_delete=models.SET_NULL,
        blank=True, null=True, default=None, related_name="reservations")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="created_reservations")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.reservation_number} ({self.status})"
