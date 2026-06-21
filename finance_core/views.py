from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
import logging

from . import serializers
from .models import Expense
from .utils.permission_classes import FinanceReportPermission
from .services.ledger_service import record_expense
from .services import report_service
from member.models import Member

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


class ExpenseView(APIView):
    def get_permissions(self):
        return [FinanceReportPermission()]

    def get(self, request):
        qs = Expense.objects.filter(is_active=True)
        module = request.query_params.get("source_module")
        if module:
            qs = qs.filter(source_module=module)
        return Response(_envelope(200, "success", "Expenses",
                        data=serializers.ExpenseSerializer(qs[:500], many=True).data))

    def post(self, request):
        s = serializers.ExpenseInputSerializer(data=request.data)
        if not s.is_valid():
            return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                            status=status.HTTP_400_BAD_REQUEST)
        vd = s.validated_data
        expense = record_expense(
            source_module=vd.get("source_module", "manual"),
            category_name=vd["category_name"], amount=vd["amount"],
            description=vd.get("description", ""), created_by=request.user)
        return Response(_envelope(201, "success", "Expense recorded",
                        data=serializers.ExpenseSerializer(expense).data),
                        status=status.HTTP_201_CREATED)


class ProfitLossView(APIView):
    permission_classes = [FinanceReportPermission]

    def get(self, request):
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        return Response(_envelope(200, "success", "Profit & Loss",
                        data=report_service.profit_and_loss(start, end)))


class IncomeBreakdownView(APIView):
    permission_classes = [FinanceReportPermission]

    def get(self, request):
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        return Response(_envelope(200, "success", "Income by particular",
                        data=report_service.income_by_particular(start, end)))


class ExpenseBreakdownView(APIView):
    permission_classes = [FinanceReportPermission]

    def get(self, request):
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        by = request.query_params.get("by", "category")
        if by == "module":
            data = report_service.expense_by_module(start, end)
        else:
            data = report_service.expense_by_category(start, end)
        return Response(_envelope(200, "success", "Expense breakdown", data=data))


class MemberStatementView(APIView):
    permission_classes = [FinanceReportPermission]

    def get(self, request, member_id):
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response(_envelope(404, "failed", "Member not found"),
                            status=status.HTTP_404_NOT_FOUND)
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        return Response(_envelope(200, "success", "Member statement",
                        data=report_service.member_statement(member, start, end)))
