"""
Provision login accounts for members so they can use the self-service portal.

Each member gets a CustomUser where:
    username = member_ID           (e.g. "SCL-00001")
    password = default (--password, defaults to "member1234")
The user is linked via Member.user and added to the "club_member" group.

Usage:
    python manage.py provision_member_logins
    python manage.py provision_member_logins --password changeme123
    python manage.py provision_member_logins --member-id SCL-00001
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from member.models import Member
from account.models import GroupModel, PermissonModel, AssignGroupPermission

User = get_user_model()

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


class Command(BaseCommand):
    help = "Create login accounts for members (self-service portal)."

    def add_arguments(self, parser):
        parser.add_argument("--password", type=str, default="member1234")
        parser.add_argument("--member-id", type=str, default=None,
                            help="Only provision this one member_ID")

    @transaction.atomic
    def handle(self, *args, **opts):
        # ensure the club_member group + its permissions exist
        group, _ = GroupModel.objects.get_or_create(name="club_member")
        for pname in MEMBER_PERMISSIONS:
            perm, _ = PermissonModel.objects.get_or_create(name=pname)
            group.permission.add(perm)

        qs = Member.objects.filter(is_active=True)
        if opts["member_id"]:
            qs = qs.filter(member_ID=opts["member_id"])

        created, linked, skipped = 0, 0, 0
        for member in qs:
            if not member.member_ID:
                skipped += 1
                continue
            if member.user_id:
                # already linked
                skipped += 1
                continue
            username = member.member_ID
            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    password=opts["password"],
                    first_name=member.first_name or "",
                    last_name=member.last_name or "",
                    is_staff=False, is_superuser=False)
                created += 1
            member.user = user
            member.save(update_fields=["user"])
            # add to club_member group
            assign, _ = AssignGroupPermission.objects.get_or_create(user=user)
            assign.group.add(group)
            linked += 1

        self.stdout.write(self.style.SUCCESS(
            f"Provisioned member logins: {created} new users, "
            f"{linked} linked, {skipped} skipped."))
        self.stdout.write(
            f"Members log in with username = member_ID, "
            f"password = '{opts['password']}'.")
