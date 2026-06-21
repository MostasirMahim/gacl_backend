from django.db import models
from member.models import Member
from django.contrib.auth import get_user_model
import pycountry
from member.models import MembershipType

COUNTRY_CHOICES = [(country.alpha_2, country.name)
                   for country in pycountry.countries]
COUNTRY_CHOICES.append(('XX', 'Unknown'))

EVENT_STATUS_CHOICES = [
    ('planned', 'Planned'),
    ('ongoing', 'Ongoing'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

EVENT_TICKET_STATUS_CHOICES = [
    ('available', 'Available'),
    ('sold_out', 'Sold Out'),
    ('reserved', 'Reserved'),
    ('cancelled', 'Cancelled'),
]


class EventBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Venue(EventBaseModel):
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state_province = models.CharField(max_length=255, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES)

    class Meta:
        unique_together = ('street_address', 'city', 'country')

    def __str__(self):
        return f"{self.street_address}, {self.city}"


class Event(EventBaseModel):
    title = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=EVENT_STATUS_CHOICES, default="planned")
    registration_deadline = models.DateTimeField()
    event_type = models.CharField(max_length=255)
    reminder_time = models.DateTimeField()
    # ForeignKey relations
    venue = models.ForeignKey(Venue, on_delete=models.RESTRICT,
                              null=True, blank=True, related_name='events_at_venue')
    organizer = models.ForeignKey(
        Member, on_delete=models.RESTRICT, null=True, blank=True, related_name='events_member')

    def __str__(self):
        return self.title


class EventMedia(EventBaseModel):
    image = models.ImageField(upload_to='event_photos/')
    # foreign_key relations
    event = models.ForeignKey(
        Event, on_delete=models.RESTRICT, related_name="event_media")

    def __str__(self):
        return f"Event Media {self.id}"


class EventTicket(EventBaseModel):

    ticket_name = models.CharField(max_length=255, unique=True)
    ticket_description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    capacity = models.PositiveIntegerField()
    start_sale_date = models.DateTimeField()
    end_sale_date = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=EVENT_TICKET_STATUS_CHOICES, default="available")
    # ForeignKey relations
    event = models.ForeignKey(
        Event, on_delete=models.RESTRICT, related_name='event_tickets')

    def __str__(self):
        return self.ticket_name


class EventFee(EventBaseModel):

    fee = models.DecimalField(max_digits=10, decimal_places=2)
    # Foreignkey relations
    event = models.ForeignKey(
        Event, on_delete=models.RESTRICT, related_name='event_fees')
    membership_type = models.ForeignKey(
        MembershipType, on_delete=models.RESTRICT, related_name='event_fees_membership_type')

    class Meta:
        unique_together = ('event', 'membership_type')

    def __str__(self):
        return str(self.fee)


# ============================================================
# EVENT COST / FOOD TRACKING (added for club management)
# Tracks what each event spends — food, logistics, talent, etc. — so an
# event's profitability (ticket income vs. expense) can be reported.
# ============================================================
class EventExpenseCategory(EventBaseModel):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class EventExpense(EventBaseModel):
    EXPENSE_KIND_CHOICES = [
        ("food", "food"),
        ("logistics", "logistics"),
        ("talent", "talent"),
        ("decoration", "decoration"),
        ("marketing", "marketing"),
        ("other", "other"),
    ]
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey(
        EventExpenseCategory, on_delete=models.PROTECT, blank=True, null=True,
        default=None, related_name="expenses")
    kind = models.CharField(
        max_length=20, choices=EXPENSE_KIND_CHOICES, default="other")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Total cost of this expense line")

    def save(self, *args, **kwargs):
        # auto-compute amount when quantity*unit_cost provided and amount unset
        if (not self.amount or self.amount == 0) and self.unit_cost:
            self.amount = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.event.title})"


class EventFoodItem(EventBaseModel):
    """Specific food items planned/managed for an event."""
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="food_items")
    name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=50, blank=True, default="")
    estimated_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    # optionally link the actual expense once incurred
    expense = models.ForeignKey(
        EventExpense, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="food_items")

    def __str__(self):
        return f"{self.name} for {self.event.title}"
