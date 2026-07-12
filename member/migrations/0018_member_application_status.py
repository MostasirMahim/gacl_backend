from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0017_member_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='application_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('draft', 'Draft'),
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='draft',
            ),
        ),
    ]
