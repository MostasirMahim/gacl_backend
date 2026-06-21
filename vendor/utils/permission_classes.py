from account.permissions import HasCustomPermission


class VendorManagementPermission(HasCustomPermission):
    required_permission = "vendor_management"
