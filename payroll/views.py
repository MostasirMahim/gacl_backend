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
from .services.payroll_service import generate_run, pay_payslip, PayrollError
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
                staff_ids=vd.get("staff_ids") or None)
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
