from account.permissions import HasCustomPermission


class PayrollManagementPermission(HasCustomPermission):
    required_permission = "payroll_management"
