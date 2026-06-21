from account.permissions import HasCustomPermission


class FinanceReportPermission(HasCustomPermission):
    required_permission = "member_financial_management"
