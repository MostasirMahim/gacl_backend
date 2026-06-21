from django.db import models
from django.conf import settings
from member_financial_management.utils.managers import ActiveManager


class PayrollBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# ------------------------------------------------------------
# Salary components: reusable definitions of earnings & deductions
# (Basic, House Rent, Medical, Transport, PF, Tax, Loan, etc.)
# ------------------------------------------------------------
class SalaryComponent(PayrollBaseModel):
    COMPONENT_TYPE_CHOICES = [
        ("earning", "earning"),
        ("deduction", "deduction"),
    ]
    CALC_TYPE_CHOICES = [
        ("fixed", "fixed"),                 # a flat amount
        ("percent_of_basic", "percent_of_basic"),  # % of basic salary
    ]
    name = models.CharField(max_length=150, unique=True)
    component_type = models.CharField(max_length=15, choices=COMPONENT_TYPE_CHOICES)
    calc_type = models.CharField(
        max_length=20, choices=CALC_TYPE_CHOICES, default="fixed")
    is_taxable = models.BooleanField(default=False)

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"{self.name} ({self.component_type})"


# ------------------------------------------------------------
# A staff member's salary structure: their basic + assigned components.
# Linked to the StaffProfile from the attendance app (1 active structure each).
# ------------------------------------------------------------
class SalaryStructure(PayrollBaseModel):
    staff = models.ForeignKey(
        "attendance.StaffProfile", on_delete=models.CASCADE,
        related_name="salary_structures")
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    effective_from = models.DateField()
    is_current = models.BooleanField(default=True)

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.staff.staff_ID} basic={self.basic_salary}"


class SalaryStructureLine(PayrollBaseModel):
    """A component attached to a structure, with its value/rate."""
    structure = models.ForeignKey(
        SalaryStructure, on_delete=models.CASCADE, related_name="lines")
    component = models.ForeignKey(
        SalaryComponent, on_delete=models.PROTECT, related_name="structure_lines")
    # for fixed -> amount; for percent_of_basic -> percentage value (e.g. 40 = 40%)
    value = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("structure", "component")

    def __str__(self):
        return f"{self.component.name}: {self.value}"


# ------------------------------------------------------------
# Payroll run: a monthly batch that generates payslips for staff.
# ------------------------------------------------------------
class PayrollRun(PayrollBaseModel):
    STATUS_CHOICES = [
        ("draft", "draft"),
        ("processed", "processed"),
        ("paid", "paid"),
        ("cancelled", "cancelled"),
    ]
    name = models.CharField(max_length=200)
    period_year = models.PositiveIntegerField()
    period_month = models.PositiveSmallIntegerField()  # 1-12
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="payroll_runs")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        unique_together = ("period_year", "period_month")
        ordering = ["-period_year", "-period_month"]

    def __str__(self):
        return f"{self.name} {self.period_month}/{self.period_year}"


class Payslip(PayrollBaseModel):
    STATUS_CHOICES = [
        ("generated", "generated"),
        ("paid", "paid"),
        ("cancelled", "cancelled"),
    ]
    run = models.ForeignKey(
        PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    staff = models.ForeignKey(
        "attendance.StaffProfile", on_delete=models.PROTECT, related_name="payslips")
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="generated")
    paid_at = models.DateTimeField(blank=True, null=True, default=None)
    note = models.TextField(blank=True, default="")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        unique_together = ("run", "staff")

    def __str__(self):
        return f"Payslip {self.staff.staff_ID} {self.run.period_month}/{self.run.period_year}"


class PayslipLine(PayrollBaseModel):
    payslip = models.ForeignKey(
        Payslip, on_delete=models.CASCADE, related_name="lines")
    component_name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=15)  # earning/deduction
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.component_name}: {self.amount}"


# Loans / advances that deduct over payslips (optional but commonly needed)
class StaffLoan(PayrollBaseModel):
    STATUS_CHOICES = [
        ("active", "active"),
        ("closed", "closed"),
    ]
    staff = models.ForeignKey(
        "attendance.StaffProfile", on_delete=models.CASCADE, related_name="loans")
    principal = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_deduction = models.DecimalField(max_digits=12, decimal_places=2)
    outstanding = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    note = models.CharField(max_length=255, blank=True, default="")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return f"Loan {self.staff.staff_ID} outstanding={self.outstanding}"
