from account.permissions import HasCustomPermission
# Auth Views form Authorization

class RegisterUserPermission(HasCustomPermission):
    required_permission = "employee_onboarding"


class GroupPermissionManagement(HasCustomPermission):
    required_permission = "group_permission_management"


class ViewAllUserPermission(HasCustomPermission):
    required_permission = "view_all_users"


class ChoicesPermission(HasCustomPermission):
    """
    Granular per-method permission for all choice endpoints.
      GET          → choice:view
      POST         → choice:create
      PATCH / PUT  → choice:update
      DELETE       → choice:delete
    """
    action_permissions = {
        "GET": "choice:view",
        "POST": "choice:create",
        "PATCH": "choice:update",
        "PUT": "choice:update",
        "DELETE": "choice:delete",
    }
