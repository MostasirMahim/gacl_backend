"""
Shared constants for the member self-service ("club_member") permission
set. Imported by both:
  - member/views.py :: ApproveMemberView (the ongoing, real approval flow)
  - member/management/commands/provision_member_logins.py (now a one-time
    backfill/migration tool only -- see that file's docstring)

Keeping this list in one place means the two places that create/extend
the "club_member" group can never drift apart the way the old
three-different-role-checks did.
"""

# Permissions a self-service member is allowed. These gate the member
# portal features. Kept intentionally small: browse menus, place & pay
# own orders/reservations, view own bills.
MEMBER_PERMISSIONS = [
    "club_member",              # marker permission
    "member_portal",            # can access the member portal
    "restaurant:view_menu",
    "restaurant:order_create",
    "outlet:view_menu",
    "outlet:order_create",
    "reservation:view",
    "reservation:create",
    "reservation:process_advance",
    "member_self:view_own_orders",
    "member_self:view_own_bills",
    "member_self:pay_own_bills",
]
