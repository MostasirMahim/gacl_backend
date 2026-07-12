from account.permissions import HasCustomPermission
# Auth Views form Authorization

class MemberManagementPermission(HasCustomPermission):
    required_permission = "member_management"


class MemberApprovePermission(HasCustomPermission):
    # The centralized path registry (account/protected_urls.py) matches
    # "/api/member/v1/members/<id>/approve/" to "member:approve" before
    # this fallback is ever consulted, but it's set for clarity / in case
    # the view is ever reached via a path the registry doesn't match.
    required_permission = "member:approve"


class MemberRejectPermission(HasCustomPermission):
    required_permission = "member:reject"
