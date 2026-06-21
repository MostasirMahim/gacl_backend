"""
Central expense ledger helper.

record_expense() is the single entry point other modules (payroll, vendor,
events, inventory) call to record an outflow in one place.
"""
import logging
from decimal import Decimal

from django.db import transaction

from finance_core.models import ExpenseCategory, Expense

logger = logging.getLogger("myapp")


@transaction.atomic
def record_expense(*, source_module, category_name, amount, description="",
                   reference_type="", reference_id=None, created_by=None):
    if amount is None or Decimal(str(amount)) <= 0:
        # nothing to record; keep callers simple
        return None
    category, _ = ExpenseCategory.objects.get_or_create(name=category_name)
    return Expense.objects.create(
        source_module=source_module, category=category,
        amount=Decimal(str(amount)), description=description,
        reference_type=reference_type, reference_id=reference_id,
        created_by=created_by,
    )
