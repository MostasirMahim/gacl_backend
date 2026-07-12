from django.db import migrations


def backfill_role(apps, schema_editor):
    """
    One-time backfill for the new CustomUser.role field.

    Rules (per master_update.md Part 3.1.A / 3.2):
      - SUPERADMIN where is_superuser=True
      - MEMBER     where Member.user already points to this user
      - STAFF      where is_staff=True, OR the user has an
                   AssignGroupPermission row but no linked Member
      - everyone else keeps the model default ("STAFF") — there should be
        no accounts left over that don't match one of the above in a
        healthy database, but we don't want a migration failure if there
        are, so unmatched rows just keep the default.

    Also flips must_change_password to False for every pre-existing
    account: the mandatory "set new password on first login" flow is
    only meant for brand-new members created via ApproveMemberView going
    forward, not for accounts that already have a working password.
    """
    CustomUser = apps.get_model('account', 'CustomUser')
    AssignGroupPermission = apps.get_model('account', 'AssignGroupPermission')
    Member = apps.get_model('member', 'Member')

    # Every existing account already has a working password -> don't force
    # a password change on next login.
    CustomUser.objects.update(must_change_password=False)

    superadmin_ids = set(
        CustomUser.objects.filter(is_superuser=True).values_list('id', flat=True)
    )
    member_user_ids = set(
        Member.objects.filter(user__isnull=False).values_list('user_id', flat=True)
    )
    staff_flagged_ids = set(
        CustomUser.objects.filter(is_staff=True).values_list('id', flat=True)
    )
    assigned_group_user_ids = set(
        AssignGroupPermission.objects.filter(user__isnull=False)
        .values_list('user_id', flat=True)
    )

    # Priority: SUPERADMIN > MEMBER > STAFF, matching the doc's ordering
    # (a Member row with user_id set is authoritative for MEMBER unless
    # that same user is also flagged is_superuser=True).
    member_ids = member_user_ids - superadmin_ids
    staff_ids = (staff_flagged_ids | (assigned_group_user_ids - member_user_ids)) - superadmin_ids

    if superadmin_ids:
        CustomUser.objects.filter(id__in=superadmin_ids).update(role='SUPERADMIN')
    if member_ids:
        CustomUser.objects.filter(id__in=member_ids).update(role='MEMBER')
    if staff_ids:
        CustomUser.objects.filter(id__in=staff_ids).update(role='STAFF')


def noop_reverse(apps, schema_editor):
    # Reversing a data backfill is not meaningful; role/must_change_password
    # simply revert to field defaults via the preceding schema migration
    # if this migration is unapplied.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0009_customuser_role_must_change_password'),
        ('member', '0017_member_user'),
    ]

    operations = [
        migrations.RunPython(backfill_role, noop_reverse),
    ]
