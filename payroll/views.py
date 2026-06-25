from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from . import serializers
from .models import (
    SalaryComponent, SalaryStructure, SalaryStructureLine, PayrollRun,
    Payslip, StaffLoan,
)
from .utils.permission_classes import PayrollManagementPermission
from .services.payroll_service import (
    generate_run, pay_payslip, adjust_payslip, PayrollError)
from core.utils.pagination import CustomPageNumberPagination

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class SalaryComponentView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [PayrollManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = SalaryComponent.objects.filter(is_active=True)
        return Response(_envelope(200, "success", "Components",
                        data=serializers.SalaryComponentSerializer(qs, many=True).data))

    def post(self, request):
        s = serializers.SalaryComponentSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(_envelope(201, "success", "Component created", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class SalaryStructureView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [PayrollManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = SalaryStructure.objects.prefetch_related("lines").filter(is_active=True)
        staff_id = request.query_params.get("staff_id")
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        return Response(_envelope(200, "success", "Structures",
                        data=serializers.SalaryStructureSerializer(qs, many=True).data))

    def post(self, request):
        s = serializers.SalaryStructureSerializer(data=request.data)
        if s.is_valid():
            structure = s.save()
            # mark previous structures for this staff non-current
            SalaryStructure.objects.filter(
                staff=structure.staff, is_current=True).exclude(
                id=structure.id).update(is_current=False)
            return Response(_envelope(201, "success", "Structure created", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class SalaryStructureLineView(APIView):
    permission_classes = [PayrollManagementPermission]

    def post(self, request):
        s = serializers.SalaryStructureLineSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(_envelope(201, "success", "Line added", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class PayrollRunView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [PayrollManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = PayrollRun.objects.prefetch_related("payslips").filter(is_active=True)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            serializers.PayrollRunSerializer(page, many=True).data)

    def post(self, request):
        s = serializers.GenerateRunSerializer(data=request.data)
        if not s.is_valid():
            return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                            status=status.HTTP_400_BAD_REQUEST)
        vd = s.validated_data
        try:
            run = generate_run(
                name=vd["name"], period_year=vd["period_year"],
                period_month=vd["period_month"], processed_by=request.user,
                staff_ids=vd.get("staff_ids") or None,
                force=vd.get("force", False))
            return Response(_envelope(201, "success", "Payroll run generated",
                            data=serializers.PayrollRunSerializer(run).data),
                            status=status.HTTP_201_CREATED)
        except PayrollError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PayslipPayView(APIView):
    permission_classes = [PayrollManagementPermission]

    def post(self, request, payslip_id):
        try:
            payslip = Payslip.objects.get(id=payslip_id)
            pay_payslip(payslip=payslip, processed_by=request.user)
            return Response(_envelope(200, "success", "Payslip paid",
                            data=serializers.PayslipSerializer(payslip).data))
        except Payslip.DoesNotExist:
            return Response(_envelope(404, "failed", "Payslip not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except PayrollError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class PayslipView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Payslip.objects.prefetch_related("lines").filter(is_active=True)
        staff_id = request.query_params.get("staff_id")
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        run_id = request.query_params.get("run_id")
        if run_id:
            qs = qs.filter(run_id=run_id)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            serializers.PayslipSerializer(page, many=True).data)


class StaffLoanView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [PayrollManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = StaffLoan.objects.filter(is_active=True)
        staff_id = request.query_params.get("staff_id")
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        return Response(_envelope(200, "success", "Loans",
                        data=serializers.StaffLoanSerializer(qs, many=True).data))

    def post(self, request):
        data = dict(request.data)
        # default outstanding to principal on creation
        if "outstanding" not in data and "principal" in data:
            data["outstanding"] = data["principal"]
        s = serializers.StaffLoanSerializer(data=data)
        if s.is_valid():
            s.save()
            return Response(_envelope(201, "success", "Loan created", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class PayslipAdjustView(APIView):
    """Bug 6.1: add an adhoc earning/deduction to a generated payslip."""
    permission_classes = [PayrollManagementPermission]

    def post(self, request, payslip_id):
        try:
            payslip = Payslip.objects.get(id=payslip_id)
        except Payslip.DoesNotExist:
            return Response(_envelope(404, "failed", "Payslip not found"),
                            status=status.HTTP_404_NOT_FOUND)
        s = serializers.AdjustPayslipSerializer(data=request.data)
        if not s.is_valid():
            return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            payslip = adjust_payslip(
                payslip=payslip,
                component_name=s.validated_data["component_name"],
                component_type=s.validated_data["component_type"],
                amount=s.validated_data["amount"])
            return Response(_envelope(200, "success", "Payslip adjusted",
                            data=serializers.PayslipSerializer(payslip).data))
        except PayrollError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class SalaryStructureDetailView(APIView):
    """Bug 6.2: update an existing salary structure (basic + lines) for a staff
    member, instead of having to build a brand-new one by copy-paste."""
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [PayrollManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return SalaryStructure.objects.prefetch_related("lines").get(id=pk)
        except SalaryStructure.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Structure not found"),
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_envelope(200, "success", "Structure detail",
                        data=serializers.SalaryStructureSerializer(obj).data))

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Structure not found"),
                            status=status.HTTP_404_NOT_FOUND)
        data = request.data
        # update simple fields
        if "basic_salary" in data:
            obj.basic_salary = data["basic_salary"]
        if "effective_from" in data and data["effective_from"]:
            obj.effective_from = data["effective_from"]
        if "is_current" in data:
            obj.is_current = bool(data["is_current"])
        obj.save()

        # optionally replace the component lines
        lines = data.get("lines")
        if isinstance(lines, list):
            obj.lines.all().delete()
            for ln in lines:
                if ln.get("component") and ln.get("value") is not None:
                    SalaryStructureLine.objects.create(
                        structure=obj, component_id=ln["component"],
                        value=ln["value"])

        if obj.is_current:
            SalaryStructure.objects.filter(
                staff=obj.staff, is_current=True).exclude(
                id=obj.id).update(is_current=False)

        obj.refresh_from_db()
        return Response(_envelope(200, "success", "Structure updated",
                        data=serializers.SalaryStructureSerializer(obj).data))

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Structure not found"),
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.is_current = False
        obj.save(update_fields=["is_active", "is_current", "updated_at"])
        return Response(_envelope(200, "success", "Structure removed"))


class SalaryStructureDetailView(APIView):
    """Bug 6.2: update an existing salary structure (basic + lines)."""
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [PayrollManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return SalaryStructure.objects.prefetch_related("lines").get(id=pk)
        except SalaryStructure.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Structure not found"),
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_envelope(200, "success", "Structure detail",
                        data=serializers.SalaryStructureSerializer(obj).data))

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Structure not found"),
                            status=status.HTTP_404_NOT_FOUND)
        data = request.data
        # update simple fields
        if "basic_salary" in data:
            obj.basic_salary = data["basic_salary"]
        if "effective_from" in data:
            obj.effective_from = data["effective_from"]
        if "is_current" in data:
            obj.is_current = bool(data["is_current"])
        obj.save()
        # if marked current, demote other structures for this staff
        if obj.is_current:
            SalaryStructure.objects.filter(
                staff=obj.staff, is_current=True).exclude(
                id=obj.id).update(is_current=False)
        # replace lines if provided
        lines = data.get("lines")
        if lines is not None:
            obj.lines.all().delete()
            for line in lines:
                SalaryStructureLine.objects.create(
                    structure=obj, component_id=line["component"],
                    value=line["value"])
        obj.refresh_from_db()
        return Response(_envelope(200, "success", "Structure updated",
                        data=serializers.SalaryStructureSerializer(obj).data))

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Structure not found"),
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return Response(_envelope(200, "success", "Structure deactivated"))
