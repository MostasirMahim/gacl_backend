from account.permissions import HasCustomPermission


class ReservationManagementPermission(HasCustomPermission):
    required_permission = "reservation_management"
