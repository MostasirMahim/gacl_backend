"""
Scheduled finance tasks.

send_monthly_due_reminders: end-of-month SMS to every member with an outstanding
balance. Wire via CELERY_BEAT_SCHEDULE (see settings) to run on the last day of
the month, or trigger manually.
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.db.models import Sum

from member_financial_management.models import Invoice
from member.models import Member
from core.utils.notifications import send_sms

logger = logging.getLogger("myapp")


def _member_phone(member) -> str:
    contacts = member.contact_numbers.filter(is_active=True)
    primary = contacts.filter(is_primary=True).first() or contacts.first()
    return getattr(primary, "number", "") or "" if primary else ""


@shared_task
def send_monthly_due_reminders():
    """Send one SMS per member who has an outstanding balance."""
    outstanding = (
        Invoice.objects.filter(
            is_active=True, status__in=["unpaid", "partial_paid", "due"])
        .values("member")
        .annotate(total_due=Sum("balance_due"))
        .filter(total_due__gt=0)
    )
    sent = 0
    for row in outstanding:
        member = Member.objects.filter(id=row["member"]).first()
        if not member:
            continue
        phone = _member_phone(member)
        if not phone:
            continue
        send_sms(
            phone,
            f"Dear member, your outstanding club dues are BDT {row['total_due']}. "
            f"Please clear them at your earliest convenience.")
        sent += 1
    logger.info("Monthly due reminders sent: %s", sent)
    return sent
