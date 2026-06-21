"""
Reservation lifecycle service.

Handles slot validation, capacity & per-member caps, overlap prevention, and
the advance-payment flow into the existing financial chain.
"""
import logging
import uuid
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.utils import timezone

from reservation.models import ReservableResource, Reservation
from core.utils.notifications import send_sms

logger = logging.getLogger("myapp")

# statuses that occupy a slot / count against caps
OCCUPYING = ("pending_payment", "confirmed")


class ReservationError(Exception):
    """Domain error (maps to HTTP 400)."""


def _generate_number() -> str:
    return "RSV-" + uuid.uuid4().hex[:12].upper()


def _overlapping_qs(resource, start_time, end_time, exclude_id=None):
    qs = Reservation.objects.filter(
        resource=resource, is_active=True, status__in=OCCUPYING,
        start_time__lt=end_time, end_time__gt=start_time)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs


@transaction.atomic
def create_reservation(*, resource, member, start_time, end_time, party_size=1,
                       note="", created_by=None):
    if end_time <= start_time:
        raise ReservationError("end_time must be after start_time.")
    if start_time < timezone.now():
        raise ReservationError("Cannot reserve a time in the past.")
    if resource.status != "open":
        raise ReservationError(f"{resource.name} is not open for reservations.")

    # within operating hours (if set)
    if resource.opening_time and start_time.time() < resource.opening_time:
        raise ReservationError("Start time is before the resource opens.")
    if resource.closing_time and end_time.time() > resource.closing_time:
        raise ReservationError("End time is after the resource closes.")

    # capacity: number of overlapping reservations must be < capacity
    overlapping = _overlapping_qs(resource, start_time, end_time).count()
    if overlapping >= resource.capacity:
        raise ReservationError(
            "No availability for this slot (capacity reached).")

    # per-member cap on simultaneous future bookings
    member_active = Reservation.objects.filter(
        resource=resource, member=member, is_active=True,
        status__in=OCCUPYING, end_time__gte=timezone.now()).count()
    if member_active >= resource.max_per_member:
        raise ReservationError(
            "You have reached the maximum simultaneous bookings for this resource.")

    reservation = Reservation.objects.create(
        reservation_number=_generate_number(),
        status="pending_payment",
        resource=resource, member=member,
        start_time=start_time, end_time=end_time, party_size=party_size,
        advance_amount=resource.advance_amount,
        advance_paid=resource.advance_amount == 0,
        note=note, created_by=created_by,
    )
    # if no advance required, confirm immediately
    if resource.advance_amount == 0:
        reservation.status = "confirmed"
        reservation.save(update_fields=["status", "updated_at"])
    return reservation


@transaction.atomic
def cancel_reservation(*, reservation):
    if reservation.status in ("cancelled", "completed"):
        raise ReservationError("Reservation is already closed.")
    reservation.status = "cancelled"
    reservation.save(update_fields=["status", "updated_at"])
    return reservation
