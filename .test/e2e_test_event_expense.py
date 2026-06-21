# Run from project root:  DJANGO_ENV=development python3 e2e_test_event_expense.py
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from member.utils.factories import MemberFactory
from event.models import Event, EventExpense, EventFoodItem
from django.db.models import Sum

PASS, FAIL = [], []
def ok(m): PASS.append(m); print("PASS:", m)
def bad(m): FAIL.append(m); print("FAIL:", m)
try:
    with transaction.atomic():
        sid = transaction.savepoint()
        now = timezone.now()
        ev = Event.objects.create(title="Mezban Night", description="d",
            start_date=now+timedelta(days=5), end_date=now+timedelta(days=5, hours=4),
            status="planned", registration_deadline=now+timedelta(days=3),
            event_type="Mezban", reminder_time=now+timedelta(days=4))
        # expense with auto-computed amount (qty*unit_cost)
        e1 = EventExpense.objects.create(event=ev, kind="food", title="Beef",
            quantity=Decimal("50"), unit_cost=Decimal("600"), amount=Decimal("0"))
        assert e1.amount == Decimal("30000.00"), e1.amount
        ok("Event expense auto-computes amount (50*600=30000)")
        EventExpense.objects.create(event=ev, kind="logistics", title="Tent", amount=Decimal("8000"))
        EventFoodItem.objects.create(event=ev, name="Kacchi", quantity=Decimal("200"),
            unit="plate", estimated_cost=Decimal("25000"))
        total = EventExpense.objects.filter(event=ev).aggregate(t=Sum("amount"))["t"]
        assert total == Decimal("38000.00"), total
        ok("Event total expense aggregates correctly (30000+8000=38000)")
        transaction.savepoint_rollback(sid)
        print("\n[rolled back]")
except Exception as e:
    import traceback; traceback.print_exc(); bad(str(e))
print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
