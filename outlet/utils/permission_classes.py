from account.permissions import HasCustomPermission


class OutletManagementPermission(HasCustomPermission):
    required_permission = "outlet_management"
