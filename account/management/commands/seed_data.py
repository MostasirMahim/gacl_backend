from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from random import choice

from member.utils.factories import *
from member.models import *
from core.models import *

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed full active member dataset with user accounts and passwords'

    def add_arguments(self, parser):
        parser.add_argument(
            '--members',
            type=int,
            default=20,
            help='Number of active full members to seed (default: 20)'
        )

    def handle(self, *args, **options):
        count = options['members']
        self.stdout.write(f'Starting full active member seed for {count} members...')

        # Ensure choice models exist
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

        # Active Membership Status Choice
        active_status = MembershipStatusChoice.objects.filter(name__iexact="active").first()
        if not active_status:
            active_status = MembershipStatusChoice.objects.create(name="active")

        # Reload saved choice objects with ids
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

        created_members = []
        user_credentials = []

        with transaction.atomic():
            for i in range(1, count + 1):
                username = f"member{i}"
                email_str = f"member{i}@gacl.test"
                password_str = "member1234"

                # Create user account for login
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email_str,
                        'first_name': fake.first_name(),
                        'last_name': fake.last_name(),
                        'is_active': True,
                    }
                )
                if user_created or not user.check_password(password_str):
                    user.set_password(password_str)
                    user.save()

                user_credentials.append((username, password_str))

                # Create Member profile
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
                        'status': 0,  # 0 = Active in STATUS_CHOICES
                        'is_active': True,
                    }
                )
                created_members.append(member)

                # Ensure Financials exist for member
                MembersFinancialBasics.objects.get_or_create(
                    member=member,
                    defaults={
                        'membership_fee': Decimal("50000"),
                        'payment_received': Decimal("50000"),
                        'membership_fee_remaining': Decimal("0"),
                        'subscription_fee': Decimal("2000"),
                        'dues_limit': Decimal("10000"),
                        'status': 0,
                        'is_active': True,
                    }
                )

                # Primary Contact Number
                ContactNumber.objects.get_or_create(
                    member=member,
                    number=f"017{i:08d}",
                    defaults={
                        'is_primary': True,
                        'contact_type': contact_types[(i - 1) % len(contact_types)],
                        'status': 0,
                        'is_active': True,
                    }
                )

                # Primary Email matching user email
                Email.objects.get_or_create(
                    member=member,
                    email=email_str,
                    defaults={
                        'is_primary': True,
                        'email_type': email_types[(i - 1) % len(email_types)],
                        'status': 0,
                        'is_active': True,
                    }
                )

        # Create full related models for each created member
        spouses = []
        descendants = []
        companions = []
        documents = []
        certificates = []
        addresses = []
        emergency_contacts = []
        jobs = []
        special_days = []

        for idx, member in enumerate(created_members):
            spouses.append(SpouseFactory.build(
                member=member,
                current_status=spouse_statuses[idx % len(spouse_statuses)]
            ))
            descendants.append(DescendantFactory.build(
                member=member,
                relation_type=descendant_relations[idx % len(descendant_relations)]
            ))
            companions.append(CompanionInformationFactory.build(member=member))
            documents.append(DocumentsFactory.build(
                member=member,
                document_type=document_types[idx % len(document_types)]
            ))
            certificates.append(CertificateFactory.build(member=member))
            addresses.append(AddressFactory.build(
                member=member,
                address_type=address_types[idx % len(address_types)]
            ))
            emergency_contacts.append(EmergencyContactFactory.build(member=member))
            jobs.append(JobFactory.build(member=member))
            special_days.append(SpecialDayFactory.build(member=member))

        Spouse.objects.bulk_create(spouses, batch_size=500)
        Descendant.objects.bulk_create(descendants, batch_size=500)
        CompanionInformation.objects.bulk_create(companions, batch_size=500)
        Documents.objects.bulk_create(documents, batch_size=500)
        Certificate.objects.bulk_create(certificates, batch_size=500)
        Address.objects.bulk_create(addresses, batch_size=500)
        EmergencyContact.objects.bulk_create(emergency_contacts, batch_size=500)
        Profession.objects.bulk_create(jobs, batch_size=500)
        SpecialDay.objects.bulk_create(special_days, batch_size=500)

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {count} active full members with user accounts!'))
        self.stdout.write(self.style.SUCCESS('User credentials: member1 .. member20 / password: member1234'))

