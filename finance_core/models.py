from django.db import models
from django.conf import settings
from member_financial_management.utils.managers import ActiveManager


class FinanceCoreBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# ------------------------------------------------------------
# Expense ledger — the missing counterpart to the existing Income model.
# Every outflow (salary, vendor purchase, event cost, inventory purchase)
# can be recorded here so the club has one place for "money out".
# ------------------------------------------------------------
class ExpenseCategory(FinanceCoreBaseModel):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class Expense(FinanceCoreBaseModel):
    # which module created it: payroll / vendor / event / restaurant / outlet / manual
    source_module = models.CharField(max_length=50, db_index=True, default="manual")
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=300, blank=True, default="")
    incurred_on = models.DateField(auto_now_add=True)
    # optional soft references (kept loose to avoid hard cross-app coupling)
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.PositiveIntegerField(blank=True, null=True, default=None)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="recorded_expenses")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-incurred_on", "-id"]

    def __str__(self):
        return f"{self.category.name}: {self.amount} ({self.source_module})"
