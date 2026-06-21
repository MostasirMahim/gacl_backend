from account.permissions import HasCustomPermission


class AttendanceManagementPermission(HasCustomPermission):
    required_permission = "attendance_management"
