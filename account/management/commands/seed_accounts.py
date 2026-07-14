from decimal import Decimal
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from faker import Faker

from member.utils.factories import *
from member.models import *
from core.models import *
from account.models import GroupModel, AssignGroupPermission
from attendance.models import StaffProfile

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Seeds testing dataset with member and staff accounts and group assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--members',
            type=int,
            default=50,
            help='Number of active full members to seed (default: 50)'
        )
        parser.add_argument(
            '--staff',
            type=int,
            default=50,
            help='Number of active staff accounts to seed (default: 50)'
        )

    def handle(self, *args, **options):
        member_count = options['members']
        staff_count = options['staff']
        self.stdout.write(f'Starting unified account seed for {member_count} members and {staff_count} staff users...')

        # 1. Ensure choice models exist
        genders = GenderFactory.create_batch(3)
        membership_types = MembershipTypeFactory.create_batch(3)
        institutes = InstituteNameFactory.create_batch(3)
        marital_statuses = MaritalStatusChoiceFactory.create_batch(3)
        contact_types = ContactTypeFactory.create_batch(3)
        email_types = EmailTypeChoiceFactory.create_batch(3)
        address_types = AddressTypeChoiceFactory.create_batch(3)
        spouse_statuses = SpouseStatusChoiceFactory.create_batch(3)
        descendant_relations = DescendantRelationChoiceFactory.create_batch(3)
        document_types = DocumentTypeChoiceFactory.create_batch(3)

        Gender.objects.bulk_create(genders, ignore_conflicts=True)
        MembershipType.objects.bulk_create(membership_types, ignore_conflicts=True)
        InstituteName.objects.bulk_create(institutes, ignore_conflicts=True)
        MaritalStatusChoice.objects.bulk_create(marital_statuses, ignore_conflicts=True)
        ContactTypeChoice.objects.bulk_create(contact_types, ignore_conflicts=True)
        EmailTypeChoice.objects.bulk_create(email_types, ignore_conflicts=True)
        AddressTypeChoice.objects.bulk_create(address_types, ignore_conflicts=True)
        SpouseStatusChoice.objects.bulk_create(spouse_statuses, ignore_conflicts=True)
        DescendantRelationChoice.objects.bulk_create(descendant_relations, ignore_conflicts=True)
        DocumentTypeChoice.objects.bulk_create(document_types, ignore_conflicts=True)

        active_status = MembershipStatusChoice.objects.filter(name__iexact="active").first()
        if not active_status:
            active_status = MembershipStatusChoice.objects.create(name="active")

        genders = list(Gender.objects.all())
        membership_types = list(MembershipType.objects.all())
        institutes = list(InstituteName.objects.all())
        marital_statuses = list(MaritalStatusChoice.objects.all())
        contact_types = list(ContactTypeChoice.objects.all())
        email_types = list(EmailTypeChoice.objects.all())
        address_types = list(AddressTypeChoice.objects.all())
        spouse_statuses = list(SpouseStatusChoice.objects.all())
        descendant_relations = list(DescendantRelationChoice.objects.all())
        document_types = list(DocumentTypeChoice.objects.all())

        member_group = GroupModel.objects.filter(name="club_member").first()

        # 2. Seed Member Accounts
        with transaction.atomic():
            for i in range(1, member_count + 1):
                username = f"member{i}"
                email_str = f"member{i}@gacl.test"
                password_str = "member1234"

                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email_str,
                        'first_name': fake.first_name(),
                        'last_name': fake.last_name(),
                        'is_active': True,
                        'is_staff': False,
                    }
                )
                if user_created or not user.check_password(password_str):
                    user.set_password(password_str)
                    user.save()

                if member_group:
                    assign_grp, _ = AssignGroupPermission.objects.get_or_create(user=user)
                    if not assign_grp.group.filter(id=member_group.id).exists():
                        assign_grp.group.add(member_group)
                        assign_grp.save()

                member_id = f"GACL-M{i:04d}"
                member, _ = Member.objects.get_or_create(
                    member_ID=member_id,
                    defaults={
                        'membership_type': membership_types[(i - 1) % len(membership_types)],
                        'gender': genders[(i - 1) % len(genders)],
                        'institute_name': institutes[(i - 1) % len(institutes)],
                        'membership_status': active_status,
                        'marital_status': marital_statuses[(i - 1) % len(marital_statuses)],
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=60),
                        'batch_number': f"B{2000 + (i % 20)}",
                        'anniversary_date': fake.date_this_century(before_today=True, after_today=False),
                        'blood_group': ['A+', 'B+', 'O+', 'AB-', 'UNKNOWN'][(i - 1) % 5],
                        'nationality': ['Bangladesh', 'India'][(i - 1) % 2],
                        'status': 0,
                        'is_active': True,
                    }
                )

                MembersFinancialBasics.objects.get_or_create(
                    member=member,
                    defaults={
                        'membership_fee': Decimal('50000.00'),
                        'payment_received': Decimal('50000.00'),
                        'membership_fee_remaining': Decimal('0.00'),
                        'subscription_fee': Decimal('2000.00'),
                        'dues_limit': Decimal('50000.00'),
                    }
                )

                ContactNumber.objects.get_or_create(
                    member=member, contact_type=contact_types[(i - 1) % len(contact_types)],
                    defaults={'number': fake.phone_number()[:14], 'is_primary': True}
                )
                Email.objects.get_or_create(
                    member=member, email_type=email_types[(i - 1) % len(email_types)],
                    defaults={'email': email_str, 'is_primary': True}
                )
                Address.objects.get_or_create(
                    member=member, address_type=address_types[(i - 1) % len(address_types)],
                    defaults={'address': fake.address()[:200]}
                )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {member_count} active member accounts."))
        self.stdout.write(f'Starting staff account seed for {staff_count} staff users...')

        # 3. Seed Staff Accounts Across Departmental Groups
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
