from django.db import migrations


def backfill_application_status(apps, schema_editor):
    """
    One-time backfill for the new Member.application_status field.

    Per master_update.md Part 3.1.B migration note, only the "already
    live" case is unambiguous:

      - user_id IS NOT NULL -> "approved" (they already have a working
        login, so by definition they were already approved under the old,
        implicit process).

    Every other existing Member row is left at the model default
    ("draft"), rather than guessed at here. The doc explicitly calls the
    "draft" vs "pending" split for pre-existing, not-yet-linked members a
    case-by-case judgment call for a human to make as a one-time data
    cleanup -- not something to encode as blanket migration logic. If your
    team decides some/all of the pre-existing unlinked Members should
    instead start as "pending" (so they immediately show up for admin
    review in the new workflow), do that as a manual follow-up data pass,
    or extend this function with your team's actual decision before
    running it.
    """
    Member = apps.get_model('member', 'Member')
    Member.objects.filter(user__isnull=False).update(
        application_status='approved')


def noop_reverse(apps, schema_editor):
    # Reversing a data backfill is not meaningful; application_status
    # simply reverts to the field default via the preceding schema
    # migration if this migration is unapplied.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0018_member_application_status'),
    ]

    operations = [
        migrations.RunPython(backfill_application_status, noop_reverse),
    ]
