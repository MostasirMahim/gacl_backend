"""
LEGACY / ONE-TIME BACKFILL TOOL ONLY.

Historically this command was the *ongoing* mechanism for turning a
Member row into a login-enabled account: run manually from the shell,
batch-provisioning every not-yet-linked Member with a shared default
password. That is no longer how member logins get created -- as of the
approve/reject workflow, `member.views.ApproveMemberView`
(`POST /api/member/v1/members/<member_id>/approve/`) is the real,
per-member, audited path: it fires as part of admin review, uses the
member's own primary phone number as the temp password, sets
`email=`/`role="MEMBER"`, sends credentials, and flips
`application_status` to "approved".

Keep this command around only for a true one-time backfill of accounts
that existed *before* the approve/reject workflow shipped (i.e. Member
rows that were never run through ApproveMemberView because it didn't
exist yet). Do not use it as an ongoing provisioning path going forward.

Two bugs fixed in this pass (previously: no `email=` set on the created
CustomUser, and no `role=` set at all):
  - `email` is now sourced from the member's primary email the same way
    ApproveMemberView does, so forgot-password isn't silently broken for
    accounts created via this command.
  - `role="MEMBER"` is now set explicitly.

Usage:
    python manage.py provision_member_logins
    python manage.py provision_member_logins --password changeme123
    python manage.py provision_member_logins --member-id SCL-00001
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from member.models import Member
from member.constants import MEMBER_PERMISSIONS
from account.models import GroupModel, PermissonModel, AssignGroupPermission

User = get_user_model()


class Command(BaseCommand):
    help = (
        "LEGACY one-time backfill: create login accounts for pre-existing "
        "members that predate the approve/reject workflow. Do not use this "
        "as the ongoing provisioning path -- see ApproveMemberView."
    )

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

            primary_email = member.emails.filter(is_primary=True).first()
            email = primary_email.email if primary_email else None

            username = member.member_ID
            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    password=opts["password"],
                    email=email,
                    first_name=member.first_name or "",
                    last_name=member.last_name or "",
                    is_staff=False, is_superuser=False, role="MEMBER")
                created += 1
            elif not user.email and email:
                # backfill email on an already-existing account too, so
                # forgot-password stops being silently broken for it.
                user.email = email
                user.role = "MEMBER"
                user.save(update_fields=["email", "role"])
            member.user = user
            member.application_status = "approved"
            member.save(update_fields=["user", "application_status"])
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
        if created:
            self.stdout.write(self.style.WARNING(
                "Reminder: this command is legacy/one-time backfill only. "
                "New member approvals should go through ApproveMemberView, "
                "not this command."))
