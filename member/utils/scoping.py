"""
Helpers for member self-service scoping.

A "member user" is a logged-in CustomUser that is linked to a Member row
(via Member.user) and is NOT staff/superuser. Such users may only see and
act on their own data. Staff/superusers are unrestricted.
"""


def get_member_for_user(user):
    """Return the Member linked to this user, or None."""
    if not user or user.is_anonymous:
        return None
    # fast path: reverse OneToOne
    member = getattr(user, "member_profile", None)
    if member is not None:
        return member
    return None


def is_member_user(user):
    """True if this user is a self-service member (not staff/admin)."""
    if not user or user.is_anonymous:
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return False
    return get_member_for_user(user) is not None


def scope_queryset_to_member(qs, user, member_field="member"):
    """
    If the user is a plain member, restrict the queryset to rows belonging
    to that member. Staff/admin users get the queryset unchanged.

    ``member_field`` is the lookup path from the model to its Member
    (e.g. "member", "reservation__member", "order__member").
    """
    if is_member_user(user):
        member = get_member_for_user(user)
        if member is None:
            return qs.none()
        return qs.filter(**{member_field: member})
    return qs
