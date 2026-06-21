# Run from project root:  DJANGO_ENV=development python3 e2e_test_payroll_vendor_finance.py
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()

from decimal import Decimal
from datetime import date
from django.db import transaction
from django.contrib.auth import get_user_model
from member.utils.factories import MemberFactory
from attendance.models import StaffProfile
from payroll.models import (SalaryComponent, SalaryStructure, SalaryStructureLine,
    PayrollRun, Payslip, StaffLoan)
from payroll.services.payroll_service import generate_run, pay_payslip, PayrollError
from vendor.models import Vendor, VendorServiceCategory, VendorServiceOffer
from vendor.services.vendor_service import select_offer, record_vendor_payment, VendorError
from finance_core.models import Expense, ExpenseCategory
from finance_core.services.report_service import profit_and_loss, expense_by_module
from finance_core.services.ledger_service import record_expense

User = get_user_model()
PASS, FAIL = [], []
def ok(m): PASS.append(m); print("PASS:", m)
def bad(m): FAIL.append(m); print("FAIL:", m)

try:
    with transaction.atomic():
        sid = transaction.savepoint()
        u = User.objects.create(username="t_admin_part4")

        # ---------- PAYROLL ----------
        staff_user = User.objects.create(username="t_staff_1")
        staff = StaffProfile.objects.create(user=staff_user, staff_ID="EMP001")
        basic = SalaryComponent.objects.create(name="HouseRent", component_type="earning",
            calc_type="percent_of_basic")
        tax = SalaryComponent.objects.create(name="Tax", component_type="deduction",
            calc_type="fixed")
        struct = SalaryStructure.objects.create(staff=staff, basic_salary=Decimal("20000"),
            effective_from=date.today(), is_current=True)
        SalaryStructureLine.objects.create(structure=struct, component=basic, value=Decimal("40"))  # 40% of basic = 8000
        SalaryStructureLine.objects.create(structure=struct, component=tax, value=Decimal("1000"))  # -1000
        # a loan: 500/month deduction
        StaffLoan.objects.create(staff=staff, principal=Decimal("5000"),
            monthly_deduction=Decimal("500"), outstanding=Decimal("5000"))

        run = generate_run(name="June Payroll", period_year=2026, period_month=6, processed_by=u)
        slip = run.payslips.first()
        # gross = 20000 + 8000 = 28000; deductions = 1000 + 500(loan) = 1500; net = 26500
        assert slip.gross_earnings == Decimal("28000.00"), slip.gross_earnings
        assert slip.total_deductions == Decimal("1500.00"), slip.total_deductions
        assert slip.net_pay == Decimal("26500.00"), slip.net_pay
        ok("Payroll calc: gross=28000, deductions=1500 (tax+loan), net=26500")

        # duplicate run for same period rejected
        try:
            generate_run(name="dup", period_year=2026, period_month=6, processed_by=u)
            bad("Duplicate payroll period should be rejected")
        except PayrollError:
            ok("Duplicate payroll period rejected")

        # pay the payslip -> loan outstanding drops, expense recorded
        pay_payslip(payslip=slip, processed_by=u)
        slip.refresh_from_db()
        loan = StaffLoan.objects.get(staff=staff)
        assert slip.status == "paid"
        assert loan.outstanding == Decimal("4500.00"), loan.outstanding
        assert Expense.objects.filter(source_module="payroll").exists()
        ok("Payslip paid: loan 5000->4500, salary expense recorded centrally")

        # ---------- VENDOR ----------
        cat = VendorServiceCategory.objects.create(name="Laundry")
        v1 = Vendor.objects.create(name="VendorA")
        v2 = Vendor.objects.create(name="VendorB")
        v3 = Vendor.objects.create(name="VendorC")
        o1 = VendorServiceOffer.objects.create(vendor=v1, category=cat, title="basic", price=Decimal("1000"))
        o2 = VendorServiceOffer.objects.create(vendor=v2, category=cat, title="basic", price=Decimal("900"))
        o3 = VendorServiceOffer.objects.create(vendor=v3, category=cat, title="basic", price=Decimal("1100"))
        select_offer(offer=o2)
        o1.refresh_from_db(); o2.refresh_from_db(); o3.refresh_from_db()
        assert o2.status == "selected" and o2.is_active
        assert o1.status == "rejected" and not o1.is_active
        assert o3.status == "rejected" and not o3.is_active
        ok("Vendor select: chosen offer active, other 2 disabled")

        # cannot pay a non-selected offer
        try:
            record_vendor_payment(offer=o1, amount=Decimal("500"), created_by=u)
            bad("Paying rejected vendor should fail")
        except VendorError:
            ok("Paying a non-selected vendor rejected")
        # pay selected -> expense recorded
        record_vendor_payment(offer=o2, amount=Decimal("900"), created_by=u)
        assert Expense.objects.filter(source_module="vendor").exists()
        ok("Vendor payment recorded as central expense")

        # ---------- FINANCE GLUE ----------
        record_expense(source_module="manual", category_name="Misc", amount=Decimal("250"), created_by=u)
        pl = profit_and_loss()
        # expenses so far: salary 26500 + vendor 900 + misc 250 = 27650 (income 0 in rolled-back test DB)
        assert pl["expense"] >= Decimal("27650"), pl["expense"]
        assert pl["net"] == pl["income"] - pl["expense"]
        ok(f"P&L unifies ledger: expense={pl['expense']}, net={pl['net']}")
        modules = {r["module"] for r in expense_by_module()}
        assert {"payroll", "vendor", "manual"}.issubset(modules), modules
        ok("Expense-by-module breakdown includes payroll, vendor, manual")

        transaction.savepoint_rollback(sid)
        print("\n[All test data rolled back - DB unchanged]")
except Exception as e:
    import traceback; traceback.print_exc(); bad(f"Unexpected: {e}")

print(f"\n===== RESULT: {len(PASS)} passed, {len(FAIL)} failed =====")
