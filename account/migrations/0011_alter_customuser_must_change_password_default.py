from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Change must_change_password default from True to False.

    Rationale: Only MEMBER accounts provisioned via ApproveMemberView
    should have must_change_password=True (set explicitly in that view
    and in seed_accounts). Staff / admin accounts must never be forced
    into the password-change screen.

    Existing rows are NOT touched — the model default only affects
    newly created accounts going forward.
    """

    dependencies = [
        ('account', '0010_backfill_customuser_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='must_change_password',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Forces a mandatory password-change screen on first login. '
                    'Set to True only for MEMBER accounts created via '
                    'ApproveMemberView (temp password = phone number).'
                ),
            ),
        ),
    ]
