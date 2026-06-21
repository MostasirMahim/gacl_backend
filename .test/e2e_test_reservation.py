# Run from project root:  DJANGO_ENV=development python3 e2e_test_reservation.py
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()

from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from member.utils.factories import MemberFactory
from reservation.models import ReservableResource, Reservation
from reservation.services.reservation_service import create_reservation, cancel_reservation, ReservationError
from reservation.services.payment_service import pay_advance

PASS, FAIL = [], []
def ok(m): PASS.append(m); print("PASS:", m)
def bad(m): FAIL.append(m); print("FAIL:", m)

try:
    with transaction.atomic():
        sid = transaction.savepoint()
        now = timezone.now()
        t1 = now + timedelta(days=1, hours=2)   # tomorrow
        t1_end = t1 + timedelta(hours=1)

        # a badminton court: capacity 1, max 2 per member, advance 200
        court = ReservableResource.objects.create(
            name="Court A", resource_type="badminton", capacity=1,
            max_per_member=2, advance_amount=Decimal("200"))
        # a pool with capacity 2
        pool = ReservableResource.objects.create(
            name="Pool 1", resource_type="pool", capacity=2,
            max_per_member=5, advance_amount=Decimal("0"))

        m1 = MemberFactory(); m2 = MemberFactory()

        # 1. basic create -> pending_payment (advance required)
        r1 = create_reservation(resource=court, member=m1, start_time=t1, end_time=t1_end)
        assert r1.status == "pending_payment", r1.status
        assert r1.advance_amount == Decimal("200")
        ok("Reservation with advance -> pending_payment")

        # 2. capacity: same slot, capacity 1 -> second member rejected
        try:
            create_reservation(resource=court, member=m2, start_time=t1, end_time=t1_end)
            bad("Overlap on full-capacity court should be rejected")
        except ReservationError:
            ok("Capacity enforced: overlapping slot rejected when full")

        # 3. non-overlapping slot is fine
        t2 = t1 + timedelta(hours=2); t2_end = t2 + timedelta(hours=1)
        r3 = create_reservation(resource=court, member=m1, start_time=t2, end_time=t2_end)
        ok("Non-overlapping slot accepted")

        # 4. per-member cap: m1 now has 2 active on court (max_per_member=2) -> 3rd rejected
        t3 = t2 + timedelta(hours=2); t3_end = t3 + timedelta(hours=1)
        try:
            create_reservation(resource=court, member=m1, start_time=t3, end_time=t3_end)
            bad("Per-member cap should reject 3rd booking")
        except ReservationError:
            ok("Per-member cap enforced (max 2 simultaneous)")

        # 5. past time rejected
        try:
            create_reservation(resource=court, member=m2,
                start_time=now - timedelta(hours=1), end_time=now)
            bad("Past reservation should be rejected")
        except ReservationError:
            ok("Past-time reservation rejected")

        # 6. advance payment confirms the booking
        inv = pay_advance(reservation=r1, payment_mode="sslcommerz")
        r1.refresh_from_db()
        assert r1.status == "confirmed" and r1.advance_paid and inv.status == "paid"
        assert inv.total_amount == Decimal("200")
        ok("Advance payment confirms reservation (invoice paid, 200)")

        # 7. double payment rejected
        try:
            pay_advance(reservation=r1, payment_mode="cash")
            bad("Double advance payment should be rejected")
        except ReservationError:
            ok("Double advance payment rejected")

        # 8. zero-advance resource auto-confirms
        rp = create_reservation(resource=pool, member=m2, start_time=t1, end_time=t1_end)
        assert rp.status == "confirmed", rp.status
        ok("Zero-advance resource auto-confirms")

        # 9. capacity 2 pool: a second overlapping booking still allowed
        rp2 = create_reservation(resource=pool, member=m1, start_time=t1, end_time=t1_end)
        assert rp2.status == "confirmed"
        ok("Capacity 2: second concurrent pool booking allowed")

        # 10. cancel frees the slot
        cancel_reservation(reservation=r1)
        r1.refresh_from_db(); assert r1.status == "cancelled"
        rX = create_reservation(resource=court, member=m2, start_time=t1, end_time=t1_end)
        ok("Cancellation frees the slot for another member")

        transaction.savepoint_rollback(sid)
        print("\n[All test data rolled back - DB unchanged]")
except Exception as e:
    import traceback; traceback.print_exc(); bad(f"Unexpected: {e}")

print(f"\n===== RESULT: {len(PASS)} passed, {len(FAIL)} failed =====")
