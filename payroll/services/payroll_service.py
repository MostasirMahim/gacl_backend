"""
Payroll calculation + payment service.

Computes gross/deductions/net for each staff member from their current salary
structure (plus loan deductions), generates payslips in a run, and on payment
records the payout into the central finance ledger as an Expense.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from payroll.models import (
    SalaryStructure, SalaryStructureLine, PayrollRun, Payslip, PayslipLine,
    StaffLoan,
)
from attendance.models import StaffProfile

logger = logging.getLogger("myapp")


class PayrollError(Exception):
    """Domain error (maps to HTTP 400)."""


def _compute_for_structure(structure):
    """
    Returns (gross_earnings, total_deductions, net_pay, lines[]) for a structure.
    lines: list of (component_name, component_type, amount)
    """
    basic = structure.basic_salary
    gross = basic
    deductions = Decimal("0")
    lines = [("Basic", "earning", basic)]

    for sl in structure.lines.select_related("component").all():
        comp = sl.component
        if comp.calc_type == "percent_of_basic":
            amount = (sl.value / Decimal("100")) * basic
        else:
            amount = sl.value
        amount = amount.quantize(Decimal("0.01"))
        if comp.component_type == "earning":
            gross += amount
        else:
            deductions += amount
        lines.append((comp.name, comp.component_type, amount))

    net = gross - deductions
    return gross, deductions, net, lines


@transaction.atomic
def generate_run(*, name, period_year, period_month, processed_by=None,
                 staff_ids=None):
    """
    Create a payroll run and generate payslips for all (or selected) staff that
    have a current salary structure. Idempotent per (year, month) via unique key.
    """
    if PayrollRun.objects.filter(
            period_year=period_year, period_month=period_month,
            is_active=True).exclude(status="cancelled").exists():
        raise PayrollError("A payroll run already exists for this period.")

    run = PayrollRun.objects.create(
        name=name, period_year=period_year, period_month=period_month,
        status="draft", processed_by=processed_by)

    structures = SalaryStructure.objects.filter(
        is_current=True, is_active=True).select_related("staff")
    if staff_ids:
        structures = structures.filter(staff_id__in=staff_ids)
    if not structures.exists():
        raise PayrollError("No current salary structures found to process.")

    grand_total = Decimal("0")
    for structure in structures:
        gross, deductions, net, lines = _compute_for_structure(structure)

        # apply active loan deductions
        loan_deduction = Decimal("0")
        loans = StaffLoan.objects.filter(
            staff=structure.staff, status="active", is_active=True)
        for loan in loans:
            take = min(loan.monthly_deduction, loan.outstanding)
            if take > 0:
                loan_deduction += take
                lines.append((f"Loan repayment ({loan.note or loan.id})",
                              "deduction", take))
        if loan_deduction > 0:
            deductions += loan_deduction
            net -= loan_deduction

        payslip = Payslip.objects.create(
            run=run, staff=structure.staff, basic_salary=structure.basic_salary,
            gross_earnings=gross, total_deductions=deductions, net_pay=net,
            status="generated")
        for name_, type_, amount_ in lines:
            PayslipLine.objects.create(
                payslip=payslip, component_name=name_,
                component_type=type_, amount=amount_)
        grand_total += net

    run.total_amount = grand_total
    run.status = "processed"
    run.save(update_fields=["total_amount", "status", "updated_at"])
    return run


@transaction.atomic
def pay_payslip(*, payslip, processed_by=None):
    """
    Mark a payslip paid, decrement any loan outstanding, and record the payout
    as a central-ledger Expense (salary).
    """
    if payslip.status == "paid":
        raise PayrollError("Payslip already paid.")
    if payslip.status == "cancelled":
        raise PayrollError("Cannot pay a cancelled payslip.")

    # decrement loan outstanding by the loan lines on this payslip
    for line in payslip.lines.filter(component_type="deduction"):
        if line.component_name.lower().startswith("loan repayment"):
            loan = StaffLoan.objects.filter(
                staff=payslip.staff, status="active", is_active=True).first()
            if loan:
                loan.outstanding = max(loan.outstanding - line.amount, Decimal("0"))
                if loan.outstanding == 0:
                    loan.status = "closed"
                loan.save(update_fields=["outstanding", "status", "updated_at"])

    payslip.status = "paid"
    payslip.paid_at = timezone.now()
    payslip.save(update_fields=["status", "paid_at", "updated_at"])

    # record salary expense in the central ledger (finance-glue app)
    try:
        from finance_core.services.ledger_service import record_expense
        record_expense(
            source_module="payroll",
            category_name="Salary",
            amount=payslip.net_pay,
            description=f"Salary {payslip.staff.staff_ID} "
                        f"{payslip.run.period_month}/{payslip.run.period_year}",
            created_by=processed_by,
        )
    except Exception as exc:  # finance-glue optional; never block payroll
        logger.warning("Could not record salary expense: %s", exc)

    # mark run paid when all payslips paid
    run = payslip.run
    if not run.payslips.exclude(status__in=["paid", "cancelled"]).exists():
        run.status = "paid"
        run.save(update_fields=["status", "updated_at"])
    return payslip
