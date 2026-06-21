"""
Central reporting: unifies the existing Income records with the new Expense
ledger to produce profit/loss style summaries, per-category and per-module,
plus per-member statements.
"""
import logging
from decimal import Decimal
from datetime import date

from django.db.models import Sum

from member_financial_management.models import Income, Invoice, Sale
from finance_core.models import Expense

logger = logging.getLogger("myapp")


def _date_filter(qs, field, start, end):
    if start:
        qs = qs.filter(**{f"{field}__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__lte": end})
    return qs


def income_total(start=None, end=None):
    qs = _date_filter(Income.objects.filter(is_active=True), "date", start, end)
    return qs.aggregate(t=Sum("actual_received"))["t"] or Decimal("0")


def expense_total(start=None, end=None):
    qs = _date_filter(Expense.objects.filter(is_active=True), "incurred_on", start, end)
    return qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")


def profit_and_loss(start=None, end=None):
    inc = income_total(start, end)
    exp = expense_total(start, end)
    return {
        "income": inc,
        "expense": exp,
        "net": inc - exp,
        "start": str(start) if start else None,
        "end": str(end) if end else None,
    }


def income_by_particular(start=None, end=None):
    qs = _date_filter(Income.objects.filter(is_active=True), "date", start, end)
    rows = (qs.values("particular__name")
              .annotate(total=Sum("actual_received"))
              .order_by("-total"))
    return [{"particular": r["particular__name"], "total": r["total"]} for r in rows]


def expense_by_category(start=None, end=None):
    qs = _date_filter(Expense.objects.filter(is_active=True), "incurred_on", start, end)
    rows = (qs.values("category__name")
              .annotate(total=Sum("amount"))
              .order_by("-total"))
    return [{"category": r["category__name"], "total": r["total"]} for r in rows]


def expense_by_module(start=None, end=None):
    qs = _date_filter(Expense.objects.filter(is_active=True), "incurred_on", start, end)
    rows = (qs.values("source_module")
              .annotate(total=Sum("amount"))
              .order_by("-total"))
    return [{"module": r["source_module"], "total": r["total"]} for r in rows]


def member_statement(member, start=None, end=None):
    """Per-member income (what they paid) + outstanding dues."""
    inc_qs = _date_filter(
        Income.objects.filter(is_active=True, member=member), "date", start, end)
    received = inc_qs.aggregate(t=Sum("actual_received"))["t"] or Decimal("0")
    due = inc_qs.aggregate(t=Sum("reaming_due"))["t"] or Decimal("0")
    invoices = _date_filter(
        Invoice.objects.filter(is_active=True, member=member), "issue_date", start, end)
    outstanding = (invoices.filter(status__in=["unpaid", "partial_paid", "due"])
                   .aggregate(t=Sum("balance_due"))["t"] or Decimal("0"))
    return {
        "member_id": member.id,
        "total_received": received,
        "period_due": due,
        "outstanding_balance": outstanding,
    }
