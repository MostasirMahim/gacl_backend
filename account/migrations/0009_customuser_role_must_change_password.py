from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0008_remove_groupmodel_club'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='role',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('SUPERADMIN', 'Superadmin'),
                    ('STAFF', 'Staff'),
                    ('MEMBER', 'Member'),
                ],
                default='STAFF',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='must_change_password',
            field=models.BooleanField(default=True),
        ),
    ]
