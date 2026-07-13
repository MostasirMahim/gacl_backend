from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from faker import Faker

from account.models import GroupModel, AssignGroupPermission
from attendance.models import StaffProfile

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Seeds testing dataset with active staff accounts and departmental group assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--staff',
            type=int,
            default=50,
            help='Number of active staff accounts to seed (default: 50)'
        )

    def handle(self, *args, **options):
        staff_count = options['staff']
        self.stdout.write(f'Starting staff account seed for {staff_count} staff users...')

        # Ensure departmental groups exist
        departmental_group_names = [
            "executive_admin", "member_services", "finance_accounts", "restaurant_kitchen",
            "outlet_operations", "facility_sports", "events_marketing", "security_gate",
            "hr_payroll", "supply_procurement"
        ]
        dept_groups = [GroupModel.objects.filter(name=g_name).first() for g_name in departmental_group_names]
        dept_groups = [g for g in dept_groups if g is not None]

        designations = [
            "General Manager", "Member Relations Officer", "Chief Accountant", "Head Chef",
            "Bar Manager", "Sports Supervisor", "Event Coordinator", "Security Supervisor",
            "HR Manager", "Procurement Officer"
        ]

        with transaction.atomic():
            for s in range(1, staff_count + 1):
                username = f"staff{s}"
                email_str = f"staff{s}@gacl.test"
                password_str = "staff1234"

                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email_str,
                        'first_name': fake.first_name(),
                        'last_name': fake.last_name(),
                        'is_active': True,
                        'is_staff': True,
                    }
                )
                if user_created or not user.check_password(password_str):
                    user.set_password(password_str)
                    user.save()

                # Assign departmental group in round-robin fashion
                if dept_groups:
                    target_group = dept_groups[(s - 1) % len(dept_groups)]
                    assign_grp, _ = AssignGroupPermission.objects.get_or_create(user=user)
                    if not assign_grp.group.filter(id=target_group.id).exists():
                        assign_grp.group.add(target_group)
                        assign_grp.save()

                StaffProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'staff_ID': f"STF-{s:04d}",
                        'designation': designations[(s - 1) % len(designations)],
                        'phone': fake.phone_number()[:14],
                        'guest_allowed': True,
                        'is_active': True,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {staff_count} active staff accounts across departmental groups."))
