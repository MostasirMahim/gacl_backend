from rest_framework import serializers
from .models import (
    SalaryComponent, SalaryStructure, SalaryStructureLine, PayrollRun,
    Payslip, PayslipLine, StaffLoan,
)


class SalaryComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryComponent
        fields = ["id", "name", "component_type", "calc_type", "is_taxable", "is_active"]


class SalaryStructureLineSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.name", read_only=True)

    class Meta:
        model = SalaryStructureLine
        fields = ["id", "structure", "component", "component_name", "value"]


class SalaryStructureSerializer(serializers.ModelSerializer):
    lines = SalaryStructureLineSerializer(many=True, read_only=True)
    staff_ID = serializers.CharField(source="staff.staff_ID", read_only=True)

    class Meta:
        model = SalaryStructure
        fields = ["id", "staff", "staff_ID", "basic_salary", "effective_from",
                  "is_current", "lines", "is_active"]


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = ["id", "component_name", "component_type", "amount"]


class PayslipSerializer(serializers.ModelSerializer):
    lines = PayslipLineSerializer(many=True, read_only=True)
    staff_ID = serializers.CharField(source="staff.staff_ID", read_only=True)

    class Meta:
        model = Payslip
        fields = ["id", "run", "staff", "staff_ID", "basic_salary",
                  "gross_earnings", "total_deductions", "net_pay", "status",
                  "paid_at", "note", "lines"]


class PayrollRunSerializer(serializers.ModelSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRun
        fields = ["id", "name", "period_year", "period_month", "status",
                  "total_amount", "processed_by", "payslips", "created_at"]


class GenerateRunSerializer(serializers.Serializer):
    name = serializers.CharField()
    period_year = serializers.IntegerField(min_value=2000, max_value=2100)
    period_month = serializers.IntegerField(min_value=1, max_value=12)
    staff_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list)
    force = serializers.BooleanField(required=False, default=False)


class AdjustPayslipSerializer(serializers.Serializer):
    component_name = serializers.CharField(max_length=255)
    component_type = serializers.ChoiceField(choices=["earning", "deduction"])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class StaffLoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffLoan
        fields = ["id", "staff", "principal", "monthly_deduction",
                  "outstanding", "status", "note", "is_active"]
