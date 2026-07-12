from core.models import Gender
from core.models import Gender, MembershipType, InstituteName, MembershipStatusChoice, MaritalStatusChoice, BLOOD_GROUPS, COUNTRY_CHOICES, ContactTypeChoice, EmailTypeChoice, AddressTypeChoice, SpouseStatusChoice, DescendantRelationChoice, DocumentTypeChoice
from rest_framework import serializers
from .models import Member, MembersFinancialBasics, ContactNumber, Email, Address, Spouse, Descendant, Profession, EmergencyContact, CompanionInformation, Documents, MemberHistory, SpecialDay, Certificate
from club.models import Club
import pdb
from .utils.utility_functions import generate_member_id
from .utils.phone import normalize_phone
from django.utils import timezone


class MemberSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, required=False)
    member_ID = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField(required=False)
    gender = serializers.CharField()
    date_of_birth = serializers.DateField()
    batch_number = serializers.CharField(required=False)
    anniversary_date = serializers.DateField(required=False, allow_null=True)
    profile_photo = serializers.ImageField(required=False)
    blood_group = serializers.CharField(required=False)
    nationality = serializers.CharField(required=False)
    membership_type = serializers.CharField()
    institute_name = serializers.CharField()
    membership_status = serializers.CharField()
    marital_status = serializers.CharField()
    # Workflow state, server-controlled only. Read-only here so it's
    # visible in responses but silently ignored on input — the client
    # cannot set/skip straight to "approved"; that only happens via the
    # dedicated ApproveMemberView. Defaults to "draft" via the model field
    # default whenever Member.objects.create() runs without it.
    application_status = serializers.CharField(read_only=True)

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            mutable_data = data.copy()
        else:
            mutable_data = dict(data)
            
        anniv = mutable_data.get('anniversary_date')
        if anniv in ['', 'null', 'undefined']:
            mutable_data['anniversary_date'] = None
            
        return super().to_internal_value(mutable_data)

    def validate_gender(self, value):
        is_exist = Gender.objects.filter(name=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"Not a valid gender")
        return value

    def validate_membership_type(self, value):

        is_exist = MembershipType.objects.filter(name=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f'{value} does not a valid membership type')
        return value

    def validate_institute_name(self, value):
        is_exist = InstituteName.objects.filter(name=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f'{value} no institute with this name exists')
        return value

    def validate_membership_status(self, value):
        is_exist = MembershipStatusChoice.objects.filter(name=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f'{value} no membership_status with this name exists')
        return value

    def validate_marital_status(self, value):
        is_exist = MaritalStatusChoice.objects.filter(name=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f'{value} no marital_status with this name exists')
        return value

    def validate_blood_group(self, value):
        if value is not None:
            valid_blood_groups = [bg[0] for bg in BLOOD_GROUPS]
            if value not in valid_blood_groups:
                raise serializers.ValidationError(
                    f"{value} is not a valid blood group")
        return value

    def validate_nationality(self, value):
        if value is not None:
            valid_countries = [cnt[1] for cnt in COUNTRY_CHOICES]
            if value not in valid_countries:
                raise serializers.ValidationError(
                    f"{value} is not a valid country")
        return value

    def validate_member_ID(self, value):
        # check if updating and instance
        if self.instance:
            membership_type = self.instance.membership_type.name
            present_id = self.instance.member_ID
            if present_id == value:
                return value

            if Member.objects.filter(membership_type__name=membership_type, member_ID=value).exists():
                raise serializers.ValidationError(
                    f"This member_ID {value} already exists for membership type {membership_type}."
                )
            return value

        # step 1: Validate format
        if '-' not in value:
            raise serializers.ValidationError(
                "Member ID must contain '-' followed by institute code (e.g. PM0001-IIT).")

        # Step 2: Split the value into two parts
        parts = value.split('-')

        # Step 3: Validate format — must have exactly 2 parts and institute code must not be empty
        if len(parts) != 2 or not parts[1].strip():
            raise serializers.ValidationError(
                "Invalid Member ID format. Expected format: PREFIX-INSTITUTE_CODE (e.g. PM0001-IIT).")

        # Step 4: Check for existing Member ID
        if Member.objects.filter(member_ID=value).exists():
            raise serializers.ValidationError(f"'{value}' ID already exists.")

        return value

    def validate(self, attrs):
        member_ID = attrs.get("member_ID")
        membership_type = attrs.get("membership_type")
        institute_name = attrs.get("institute_name")
        institute_code = member_ID.split('-')[1]
        print(institute_code, "institute_code")
        if not member_ID.startswith(membership_type):
            raise serializers.ValidationError(
                {"member_ID": "Invalid member_ID"})
        if not InstituteName.objects.filter(name=institute_name, code=institute_code).exists():
            raise serializers.ValidationError(
                {"member_ID": "Invalid institute name or code"})
        request = self.context.get("request")
        if request and request.method == "POST":
            if not attrs.get("profile_photo"):
                raise serializers.ValidationError({
                    "profile_photo": "This field is required when creating a member."
                })

        return super().validate(attrs)

    def create(self, validated_data):
        gender_data = validated_data.pop('gender')
        membership_type_data = validated_data.pop('membership_type')
        institute_name_data = validated_data.pop('institute_name')
        membership_status_data = validated_data.pop('membership_status')
        marital_status_data = validated_data.pop('marital_status')
        gender = Gender.objects.get(name=gender_data)
        membership_type = MembershipType.objects.get(name=membership_type_data)
        institute_name = InstituteName.objects.get(name=institute_name_data)
        membership_status = MembershipStatusChoice.objects.get(
            name=membership_status_data)
        marital_status = MaritalStatusChoice.objects.get(
            name=marital_status_data)
        member = Member.objects.create(
            gender=gender, membership_type=membership_type, institute_name=institute_name,
            membership_status=membership_status, marital_status=marital_status,
            # Completing this wizard/form IS the act of submitting the
            # application for review -- there's no separate partial-save
            # concept today, so a freshly-created Member should be
            # immediately visible on the Pending Members page rather than
            # silently sitting at the model's "draft" default forever with
            # no path to promote it.
            application_status="pending",
            **validated_data)
        return member

    def update(self, instance, validated_data):
        old_id = instance.member_ID
        member_ID = validated_data.get('member_ID', instance.member_ID)
        membership_type = validated_data.get(
            'membership_type', instance.membership_type)
        first_name = validated_data.get('first_name', instance.first_name)
        last_name = validated_data.get('last_name', instance.last_name)
        gender = validated_data.get('gender', instance.gender)
        date_of_birth = validated_data.get(
            'date_of_birth', instance.date_of_birth)
        batch_number = validated_data.get(
            'batch_number', instance.batch_number)
        anniversary_date = validated_data.get(
            'anniversary_date', instance.anniversary_date)
        profile_photo = validated_data.get(
            'profile_photo', instance.profile_photo)
        blood_group = validated_data.get('blood_group', instance.blood_group)
        nationality = validated_data.get('nationality', instance.nationality)
        institute_name = validated_data.get(
            'institute_name', instance.institute_name)
        membership_status = validated_data.get(
            'membership_status', instance.membership_status)
        marital_status = validated_data.get(
            'marital_status', instance.marital_status)

        # get dependencies
        membership_type_obj = MembershipType.objects.get(name=membership_type)

        gender = Gender.objects.get(name=gender)
        institute_name = InstituteName.objects.get(name=institute_name)
        membership_status = MembershipStatusChoice.objects.get(
            name=membership_status)
        marital_status = MaritalStatusChoice.objects.get(
            name=marital_status)

        flag = False
        if instance.member_ID != member_ID:
            flag = True
        # update information
        instance.member_ID = member_ID
        instance.first_name = first_name
        instance.last_name = last_name
        instance.gender = gender
        instance.date_of_birth = date_of_birth
        instance.batch_number = batch_number
        instance.anniversary_date = anniversary_date
        instance.profile_photo = profile_photo
        instance.blood_group = blood_group
        instance.nationality = nationality
        instance.membership_type = membership_type_obj
        instance.marital_status = marital_status
        instance.institute_name = institute_name
        instance.membership_status = membership_status
        # save the instance
        instance.save()
        if flag:
            old_records = MemberHistory.objects.filter(member=instance)
            update_lst = []
            for record in old_records:
                record.end_date = timezone.now()
                update_lst.append(record)
            MemberHistory.objects.bulk_update(update_lst, ['end_date'])
            history = MemberHistory(
                start_date=timezone.now(),
                stored_member_id=old_id,
                transferred=True,
                transferred_reason="updated",
                member=instance
            )
            # save member history instance
            history.save()

        return instance


class MembersFinancialBasicsSerializer(serializers.Serializer):
    membership_fee = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2)
    payment_received = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2)
    membership_fee_remaining = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2)
    subscription_fee = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2)
    dues_limit = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2)
    initial_payment_doc = serializers.FileField(
        required=False)

    def create(self, validated_data):
        member_ID = validated_data.pop("member_ID")
        member = Member.objects.get(member_ID=member_ID)
        member_financial_basics = MembersFinancialBasics.objects.create(member=member,
                                                                        **validated_data)

        return member_financial_basics

    def update(self, instance, validated_data):
        # get the data from instance or
        membership_fee = validated_data.get(
            'membership_fee', instance.membership_fee)
        payment_received = validated_data.get(
            'payment_received', instance.payment_received)
        membership_fee_remaining = validated_data.get(
            'membership_fee_remaining', instance.membership_fee_remaining)
        subscription_fee = validated_data.get(
            'subscription_fee', instance.subscription_fee)
        dues_limit = validated_data.get('dues_limit', instance.dues_limit)
        initial_payment_doc = validated_data.get(
            'initial_payment_doc', instance.initial_payment_doc)

        # update the instance
        instance.membership_fee = membership_fee
        instance.payment_received = payment_received
        instance.membership_fee_remaining = membership_fee_remaining
        instance.subscription_fee = subscription_fee
        instance.dues_limit = dues_limit
        instance.initial_payment_doc = initial_payment_doc
        instance.save()

        return instance


class MemberIdSerializer(serializers.Serializer):
    membership_type = serializers.CharField()
    institute_name = serializers.CharField()

    def validate_membership_type(self, value):
        is_type_exist = MembershipType.objects.filter(name=value).exists()

        if not is_type_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid membership type")
        return value

    def validate_institute_name(self, value):
        value = value.title()
        is_type_exist = InstituteName.objects.filter(name=value).first()
        if not is_type_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid institute name")
        return is_type_exist.code


class MemberSerializerForViewSingleMember(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = "__all__"
        depth = 1


class MembersFinancialBasicsSerializerForViewSingleMember(serializers.ModelSerializer):
    class Meta:
        model = MembersFinancialBasics
        exclude = ['id', 'member', 'status', 'created_at', 'updated_at']


class ContactDetailSerializer(serializers.Serializer):
    contact_type = serializers.PrimaryKeyRelatedField(
        queryset=ContactTypeChoice.objects.all(), required=False)
    number = serializers.CharField(max_length=20)
    is_primary = serializers.BooleanField(required=False)
    id = serializers.IntegerField(required=False)


class MemberContactNumberSerializer(serializers.Serializer):
    member_ID = serializers.CharField(required=True)
    data = serializers.ListSerializer(
        child=ContactDetailSerializer(), required=True)

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def validate_data(self, value):
        """Ensure only one item in data has is_primary=True"""
        primary_count = sum(
            1 for item in value if item.get("is_primary", False))

        if primary_count > 1:
            raise serializers.ValidationError(
                "Only one contact can be marked as primary.")
        return value

    def validate(self, attrs):
        """
        Duplicate-number check (member/models.py :: ContactNumber.number
        has no uniqueness constraint at all today -- two different
        members can share an identical number with no warning). Compares
        normalized (E.164) forms so "+8801712345678" and "01712345678"
        are recognized as the same number.

        Note: this does a full table scan over ContactNumber to compare
        normalized forms, since there's no normalized/indexed column to
        query against directly. Fine at current club-membership scale;
        if this table grows very large, consider adding a normalized,
        indexed column populated on save instead.
        """
        data_list = attrs.get("data", [])
        seen_in_request = set()
        existing_qs = ContactNumber.objects.exclude(
            number__isnull=True).exclude(number="")
        if self.instance is not None:
            # self.instance is the Member being updated; don't flag a
            # member's own existing numbers as duplicates of themselves.
            existing_qs = existing_qs.exclude(member=self.instance)
        existing_normalized = {
            normalize_phone(num) for num in existing_qs.values_list("number", flat=True)
        }

        for item in data_list:
            number = item.get("number")
            if not number:
                continue
            normalized = normalize_phone(number)
            if normalized in seen_in_request:
                raise serializers.ValidationError(
                    {"data": [f"Duplicate contact number in this request: {number}"]})
            seen_in_request.add(normalized)
            if normalized in existing_normalized:
                raise serializers.ValidationError(
                    {"data": [f"This contact number ({number}) is already registered to another member."]})

        return super().validate(attrs)

    def create(self, validated_data):
        member_ID = validated_data["member_ID"]
        data = validated_data["data"]
        member = Member.objects.get(member_ID=member_ID)
        created_instances = []
        for item in data:
            ins = ContactNumber.objects.create(**item, member=member)
            created_instances.append({
                "status": "created",
                "contact_number_id": ins.id
            })
        return created_instances

    def update(self, instance, validated_data):
        """
        instance: A Member instance whose contact_numbers will be updated.
        validated_data: Dictionary containing:
            - member_ID (string)
            - data: A list of contact details (each may include an "id" if updating an existing contact)
        """
        data_list = validated_data.get('data', [])
        results = []
        all_con_num_obj = instance.contact_numbers.all()
        all_con_num_data = {obj.id: obj for obj in all_con_num_obj}

        for item in data_list:
            contact_id = item.get('id', None)
            if contact_id:
                contact_obj = all_con_num_data.get(contact_id)
                if not contact_obj:
                    raise serializers.ValidationError(
                        f"Contact with id {contact_id} does not exist for this member."
                    )

                changed = False

                if 'contact_type' in item and item['contact_type'] != contact_obj.contact_type:
                    contact_obj.contact_type = item['contact_type']
                    changed = True
                if 'number' in item and item['number'] != contact_obj.number:
                    contact_obj.number = item['number']
                    changed = True
                if 'is_primary' in item and item['is_primary'] != contact_obj.is_primary:
                    contact_obj.is_primary = item['is_primary']
                    changed = True

                if changed:
                    contact_obj.save()
                    results.append({
                        "status": "updated",
                        "contact_number_id": contact_obj.id
                    })
                else:
                    results.append({
                        "status": "no_change",
                        "contact_number_id": contact_obj.id
                    })

            else:
                # Create a new contact number if no ID is provided
                new_contact = ContactNumber.objects.create(
                    member=instance, **item)
                results.append({
                    "status": "created",
                    "contact_number_id": new_contact.id
                })

        return results


class MemberContactNumberDeleteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=ContactNumber.objects.all())


class EmailAddressSerializer(serializers.Serializer):
    email_type = serializers.PrimaryKeyRelatedField(
        queryset=EmailTypeChoice.objects.all(), required=False)
    email = serializers.EmailField()
    is_primary = serializers.BooleanField(required=False)
    id = serializers.IntegerField(required=False)


class MemberEmailAddressSerializer(serializers.Serializer):
    member_ID = serializers.CharField(required=True)
    data = serializers.ListSerializer(
        child=EmailAddressSerializer(), required=True)

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def validate_data(self, value):
        """Ensure only one item in data has is_primary=True"""
        primary_count = sum(
            1 for item in value if item.get("is_primary", False))

        if primary_count > 1:
            raise serializers.ValidationError(
                "Only one contact can be marked as primary.")
        return value

    def validate(self, attrs):
        """
        Duplicate-email pre-check. member.Email.email has unique=True at
        the DB level but there was no pre-check here, so a duplicate
        raised a raw IntegrityError (500) instead of a clean validation
        error. This returns a clean 400 instead.
        """
        data_list = attrs.get("data", [])
        seen_in_request = set()
        existing_qs = Email.objects.all()
        if self.instance is not None:
            # self.instance is the Member being updated; don't flag a
            # member's own existing email as a duplicate of itself.
            existing_qs = existing_qs.exclude(member=self.instance)

        for item in data_list:
            email = item.get("email")
            if not email:
                continue
            normalized_email = email.strip().lower()
            if normalized_email in seen_in_request:
                raise serializers.ValidationError(
                    {"data": [f"Duplicate email in this request: {email}"]})
            seen_in_request.add(normalized_email)
            if existing_qs.filter(email__iexact=email).exists():
                raise serializers.ValidationError(
                    {"data": [f"This email ({email}) is already registered to another member."]})

        return super().validate(attrs)

    def create(self, validated_data):
        member_ID = validated_data["member_ID"]
        data = validated_data["data"]
        member = Member.objects.get(member_ID=member_ID)
        created_instances = []
        for item in data:
            ins = Email.objects.create(**item, member=member)
            created_instances.append({
                "status": "created",
                "email_address_id": ins.id
            })
        return created_instances

    def update(self, instance, validated_data):
        data_list = validated_data.get('data', [])
        results = []
        updated = False

        existing_emails = {email.id: email for email in instance.emails.all()}

        for item in data_list:
            email_id = item.get('id', None)
            if email_id:
                email_obj = existing_emails.get(email_id)
                if not email_obj:
                    raise serializers.ValidationError(
                        f"email with id {email_id} does not exist for this member."
                    )

                if 'email_type' in item and item['email_type'] != email_obj.email_type:
                    email_obj.email_type = item['email_type']
                    updated = True
                if 'email' in item and item['email'] != email_obj.email:
                    email_obj.email = item['email']
                    updated = True
                if 'is_primary' in item and item['is_primary'] != email_obj.is_primary:
                    email_obj.is_primary = item['is_primary']
                    updated = True

                if updated:
                    email_obj.save()
                    results.append({
                        "status": "updated",
                        "email_id": email_obj.id
                    })
                else:
                    results.append({
                        "status": "no_change",
                        "email_id": email_obj.id
                    })
            else:
                new_email = Email.objects.create(member=instance, **item)
                results.append({
                    "status": "created",
                    "email_id": new_email.id
                })

        return results


class MemberEmailAddressDeleteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Email.objects.all())


class AddressSerializer(serializers.Serializer):
    address_type = serializers.PrimaryKeyRelatedField(
        queryset=AddressTypeChoice.objects.all(), required=False)
    address = serializers.CharField()
    is_primary = serializers.BooleanField(required=False)
    title = serializers.CharField(max_length=100, required=False)
    id = serializers.IntegerField(required=False)


class MemberAddressSerializer(serializers.Serializer):
    member_ID = serializers.CharField(required=True)
    data = serializers.ListSerializer(
        child=AddressSerializer(), required=True)

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def validate_data(self, value):
        """Ensure only one item in data has is_primary=True"""
        primary_count = sum(
            1 for item in value if item.get("is_primary", False))

        if primary_count > 1:
            raise serializers.ValidationError(
                "Only one contact can be marked as primary.")
        return value

    def create(self, validated_data):
        member_ID = validated_data["member_ID"]
        data = validated_data["data"]
        member = Member.objects.get(member_ID=member_ID)
        created_instances = []
        for item in data:
            ins = Address.objects.create(**item, member=member)
            created_instances.append({
                "status": "created",
                "address_id": ins.id
            })
        return created_instances

    def update(self, instance, validated_data):
        """
        instance: A Member instance whose address will be updated.
        validated_data: Dictionary containing:
            - member_ID (string)
            - data: A list of addresses (each may include an "id" if updating an existing address)
        """
        data_list = validated_data.get('data', [])
        results = []
        all_mem_address = instance.addresses.all()
        all_mem_data = {address.id: address for address in all_mem_address}
        # pdb.set_trace()

        for item in data_list:
            address_id = item.get('id', None)
            if address_id:
                address_obj = all_mem_data.get(address_id)
                if not address_obj:
                    raise serializers.ValidationError(
                        f"Address with id {address_id} does not exist for this member."
                    )

                changed = False

                if 'address_type' in item and item['address_type'] != address_obj.address_type:
                    address_obj.address_type = item['address_type']
                    changed = True
                if 'address' in item and item['address'] != address_obj.address:
                    address_obj.address = item['address']
                    changed = True
                if 'title' in item and item['title'] != address_obj.title:
                    address_obj.title = item['title']
                    changed = True
                if 'is_primary' in item and item['is_primary'] != address_obj.is_primary:
                    address_obj.is_primary = item['is_primary']
                    changed = True

                if changed:
                    address_obj.save()
                    results.append({
                        "status": "updated",
                        "address_id": address_obj.id
                    })
                else:
                    results.append({
                        "status": "no_change",
                        "address_id": address_obj.id
                    })

            else:
                # Create a new address if no ID is provided
                address = Address.objects.create(member=instance, **item)
                results.append({
                    "status": "created",
                    "address_id": address.id
                })

        return results


class MemberAddressDeleteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all())


class MemberSpouseSerializer(serializers.Serializer):
    spouse_name = serializers.CharField(max_length=100)
    contact_number = serializers.CharField(max_length=20, required=False)
    spouse_dob = serializers.DateField(required=False)
    image = serializers.ImageField(required=False)
    current_status = serializers.PrimaryKeyRelatedField(
        queryset=SpouseStatusChoice.objects.all(), required=False)
    member_ID = serializers.CharField()
    id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['image'].required = False

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def create(self, validated_data):
        spouse_name = validated_data['spouse_name']
        contact_number = validated_data.get("contact_number", "")
        spouse_dob = validated_data.get("spouse_dob")
        image = validated_data.get("image")
        current_status = validated_data.get("current_status")
        member_ID = validated_data['member_ID']
        member = Member.objects.get(member_ID=member_ID)
        instance = Spouse.objects.create(spouse_name=spouse_name, spouse_contact_number=contact_number,
                                         spouse_dob=spouse_dob, image=image, current_status=current_status, member=member)
        return instance

    def update(self, instance, validated_data):
        id = validated_data.get("id")
        is_update = False
        if id is not None:
            spouse_obj = instance
            if 'spouse_name' in validated_data and spouse_obj.spouse_name != validated_data.get('spouse_name', spouse_obj.spouse_name):
                spouse_obj.spouse_name = validated_data['spouse_name']
                is_update = True

            if 'contact_number' in validated_data and spouse_obj.spouse_contact_number != validated_data.get('contact_number', spouse_obj.spouse_contact_number):
                is_update = True
                spouse_obj.spouse_contact_number = validated_data['contact_number']

            if 'spouse_dob' in validated_data and spouse_obj.spouse_dob != validated_data.get('spouse_dob', spouse_obj.spouse_dob):
                is_update = True
                spouse_obj.spouse_dob = validated_data['spouse_dob']

            if 'image' in validated_data and spouse_obj.image != validated_data.get('image', spouse_obj.image):
                is_update = True
                spouse_obj.image = validated_data['image']

            if 'current_status' in validated_data and spouse_obj.current_status != validated_data.get('current_status', spouse_obj.current_status):
                is_update = True
                spouse_obj.current_status = validated_data['current_status']

            if 'is_active' in validated_data and spouse_obj.is_active != validated_data.get('is_active', spouse_obj.is_active):
                is_update = True
                spouse_obj.is_active = validated_data['is_active']

            if is_update:
                spouse_obj.save(update_fields=[
                                "spouse_name", "spouse_contact_number", "spouse_dob", "image", "current_status", "is_active"])
                return spouse_obj

        return instance


class MemberSpecialDayDataSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100)
    date = serializers.DateField(required=False)
    id = serializers.IntegerField(required=False)


class MemberSpecialDaySerializer(serializers.Serializer):
    member_ID = serializers.CharField(max_length=200)
    data = serializers.ListSerializer(
        child=MemberSpecialDayDataSerializer(), required=True)

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def create(self, validated_data):
        member_ID = validated_data['member_ID']
        data = validated_data['data']
        member = Member.objects.get(member_ID=member_ID)

        created_instances = []
        for item in data:
            instance = SpecialDay.objects.create(**item, member=member)
            created_instances.append({
                "status": "created",
                "special_day_id": instance.id
            })

        return created_instances

    def update(self, instance, validated_data):
        data_list = validated_data.get('data', [])
        results = []

        special_days_qs = instance.special_days.all()
        special_day_dict = {sd.id: sd for sd in special_days_qs}

        for item in data_list:
            special_day_id = item.get('id', None)
            if special_day_id:
                special_day_obj = special_day_dict.get(special_day_id)
                if not special_day_obj:
                    raise serializers.ValidationError(
                        f"Special day with id {special_day_id} does not exist for this member."
                    )
                # Check if any field actually changed
                changed = False

                if 'title' in item and item['title'] != special_day_obj.title:
                    special_day_obj.title = item['title']
                    changed = True
                if 'date' in item and item['date'] != special_day_obj.date:
                    special_day_obj.date = item['date']
                    changed = True

                if changed:
                    special_day_obj.save()
                    results.append({
                        "status": "updated",
                        "special_day_id": special_day_obj.id
                    })
                else:
                    results.append({
                        "status": "no_change",
                        "special_day_id": special_day_obj.id
                    })

            else:
                # create new special day
                new_special_day = SpecialDay.objects.create(
                    member=instance, **item)
                results.append({
                    "status": "created",
                    "special_day_id": new_special_day.id
                })

        return results


class MemberSpecialDayDeleteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=SpecialDay.objects.all())


class MemberCertificateSerializer(serializers.Serializer):
    member_ID = serializers.CharField(max_length=200)
    title = serializers.CharField(max_length=100)
    certificate_number = serializers.CharField(max_length=100, required=False)
    certificate_document = serializers.FileField()
    id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['certificate_document'].required = False

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def validate_certificate_number(self, value):
        if not value.isalnum():
            raise serializers.ValidationError(
                "Certificate number must contain only letters and numbers.")
        return value

    def create(self, validated_data):
        member_ID = validated_data.pop('member_ID')
        member = Member.objects.get(member_ID=member_ID)
        instance = Certificate.objects.create(member=member, **validated_data)
        return instance

    def update(self, instance, validated_data):
        id = validated_data.get("id")
        if id is not None:
            certificate_obj = instance
            certificate_obj.title = validated_data.get(
                "title", certificate_obj.title)
            certificate_obj.certificate_number = validated_data.get(
                "certificate_number", certificate_obj.certificate_number)
            certificate_obj.certificate_document = validated_data.get(
                "certificate_document", certificate_obj.certificate_document)
            certificate_obj.is_active = validated_data.get(
                "is_active", certificate_obj.is_active)
            certificate_obj.save(update_fields=[
                                 "title", "certificate_number", "certificate_document", "is_active"])
        else:
            member_ID = validated_data.pop("member_ID")
            if Member.objects.filter(member_ID=member_ID).exists():
                raise serializers.ValidationError(
                    "No member exists with this id")
            member = Member.objects.get(member_ID=member_ID)
            instance = Certificate.objects.create(
                **validated_data, member=member)
        return instance


class MemberDescendantsSerializer(serializers.Serializer):
    member_ID = serializers.CharField()
    descendant_contact_number = serializers.CharField(
        max_length=20, required=False)
    dob = serializers.DateField(required=False)
    image = serializers.ImageField(required=False)
    relation_type = serializers.PrimaryKeyRelatedField(
        queryset=DescendantRelationChoice.objects.all(), required=False)
    name = serializers.CharField(max_length=100)
    id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['image'].required = False

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def create(self, validated_data):
        id = validated_data.get("id")
        if id is not None:
            validated_data.pop("id")
        member_ID = validated_data.pop("member_ID")
        member = Member.objects.get(member_ID=member_ID)
        instance = Descendant.objects.create(**validated_data, member=member)
        return instance

    def update(self, instance, validated_data):
        id = validated_data.get("id")
        response_data = []
        if id is not None:
            is_updated = False

            descendant_obj = instance
            if "descendant_contact_number" in validated_data and descendant_obj.descendant_contact_number != validated_data.get("descendant_contact_number"):
                descendant_obj.descendant_contact_number = validated_data.get(
                    "descendant_contact_number")
                is_updated = True
            if "dob" in validated_data and descendant_obj.dob != validated_data.get("dob"):
                descendant_obj.dob = validated_data.get("dob")
                is_updated = True

            if "image" in validated_data and descendant_obj.image != validated_data.get("image"):
                descendant_obj.image = validated_data.get("image")
                is_updated = True

            if "relation_type" in validated_data and descendant_obj.relation_type != validated_data.get("relation_type"):
                descendant_obj.relation_type = validated_data.get(
                    "relation_type")
                is_updated = True
            if "name" in validated_data and descendant_obj.name != validated_data.get("name"):
                descendant_obj.name = validated_data.get("name")
                is_updated = True
            if "is_active" in validated_data and descendant_obj.is_active != validated_data.get("is_active"):
                descendant_obj.is_active = validated_data.get("is_active")
                is_updated = True

            if is_updated:
                descendant_obj.save(update_fields=[
                                    "descendant_contact_number", "dob", "image", "relation_type", "name", "is_active"])
                return descendant_obj

        return instance


class MemberJobDataSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100)
    organization_name = serializers.CharField(max_length=150, required=False)
    location = serializers.CharField(max_length=100)
    job_description = serializers.CharField(required=False)
    location = serializers.CharField(max_length=100, required=False)
    id = serializers.IntegerField(required=False)


class MemberJobSerializer(serializers.Serializer):
    member_ID = serializers.CharField(max_length=200)
    data = serializers.ListSerializer(
        child=MemberJobDataSerializer(), required=True)

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def create(self, validated_data):
        member_ID = validated_data.pop('member_ID')
        data = validated_data.pop('data')
        member = Member.objects.get(member_ID=member_ID)
        created_instance = []
        for job_data in data:
            instance = Profession.objects.create(**job_data, member=member)
            created_instance.append({
                'status': 'created',
                'job_id': instance.id
            })
        return created_instance

    def update(self, instance, validated_data):
        """
        instance: A Member instance whose Job will be updated.
        validated_data: Dictionary containing:
            - member_ID (string)
            - data: A list of title (each may include an "id" if updating an existing job)
        """
        data_list = validated_data.get('data', [])
        results = []

        # Get all current professions for the member
        all_job_instance = instance.professions.all()
        all_job_data = {job.id: job for job in all_job_instance}

        for item in data_list:
            job_id = item.get('id', None)
            if job_id:
                # Update an existing job
                job_obj = all_job_data.get(job_id)
                print(job_obj, "job obj")
                if job_obj is None:
                    raise serializers.ValidationError(
                        f"Job with id {job_id} does not exist for this member."
                    )

                # Check if any field actually changed
                changed = False

                if 'title' in item and item['title'] != job_obj.title:
                    job_obj.title = item['title']
                    changed = True
                if 'organization_name' in item and item['organization_name'] != job_obj.organization_name:
                    job_obj.organization_name = item['organization_name']
                    changed = True
                if 'job_description' in item and item['job_description'] != job_obj.job_description:
                    job_obj.job_description = item['job_description']
                    changed = True
                if 'location' in item and item['location'] != job_obj.location:
                    job_obj.location = item['location']
                    changed = True

                if changed:
                    job_obj.save()
                    results.append({
                        "status": "updated",
                        "job_id": job_obj.id
                    })
                else:
                    results.append({
                        "status": "no_change",
                        "job_id": job_obj.id
                    })

            else:
                # Create a new job
                job = Profession.objects.create(member=instance, **item)
                results.append({
                    "status": "created",
                    "job_id": job.id
                })

        return results


class MemberJobDeleteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Profession.objects.all())


class MemberEmergencyContactDataSerializer(serializers.Serializer):
    contact_name = serializers.CharField(max_length=100)
    contact_number = serializers.CharField(max_length=20)
    relation_with_member = serializers.CharField(max_length=50, required=False)
    id = serializers.IntegerField(required=False)


class MemberEmergencyContactSerializer(serializers.Serializer):
    member_ID = serializers.CharField()
    data = serializers.ListSerializer(
        child=MemberEmergencyContactDataSerializer(), required=True)

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def create(self, validated_data):
        member_ID = validated_data.pop("member_ID")
        data = validated_data.pop("data")
        member = Member.objects.get(member_ID=member_ID)
        created_instance = []
        for emergency_contact_data in data:
            instance = EmergencyContact.objects.create(
                **emergency_contact_data, member=member)
            created_instance.append({
                'status': "created",
                'emergency_contact_id': instance.id
            })
        return created_instance

    def update(self, instance, validated_data):
        """
        instance: A Member instance whose Emergency contact will be updated.
        validated_data: Dictionary containing:
            - member_ID (string)
            - data: A list of contacts (each may include an "id" if updating an existing emergency contact)
        """
        data_list = validated_data.get('data', [])
        results = []

        all_em_con_instance = instance.emergency_contacts.all()
        all_em_con_data = {em_con.id: em_con for em_con in all_em_con_instance}

        for item in data_list:
            emergency_contact_id = item.get('id', None)
            if emergency_contact_id:
                # Update an existing emergency contact
                emergency_contact_obj = all_em_con_data.get(
                    emergency_contact_id)
                if emergency_contact_obj is None:
                    raise serializers.ValidationError(
                        f"Emergency contact with id {emergency_contact_id} does not exist for this member."
                    )

                # Check if any field actually changed
                changed = False

                if 'contact_name' in item and item['contact_name'] != emergency_contact_obj.contact_name:
                    emergency_contact_obj.contact_name = item['contact_name']
                    changed = True
                if 'contact_number' in item and item['contact_number'] != emergency_contact_obj.contact_number:
                    emergency_contact_obj.contact_number = item['contact_number']
                    changed = True
                if 'relation_with_member' in item and item['relation_with_member'] != emergency_contact_obj.relation_with_member:
                    emergency_contact_obj.relation_with_member = item['relation_with_member']
                    changed = True

                if changed:
                    emergency_contact_obj.save()
                    results.append({
                        "status": "updated",
                        "emergency_contact_id": emergency_contact_obj.id
                    })
                else:
                    results.append({
                        "status": "no_change",
                        "emergency_contact_id": emergency_contact_obj.id
                    })

            else:
                # Create a new emergency contact
                emergency_contact = EmergencyContact.objects.create(
                    member=instance, **item)
                results.append({
                    "status": "created",
                    "emergency_contact_id": emergency_contact.id
                })

        return results


class MemberEmergencyContactDeleteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=EmergencyContact.objects.all())


class MemberCompanionInformationSerializer(serializers.Serializer):
    member_ID = serializers.CharField(max_length=200)
    companion_name = serializers.CharField(max_length=100)
    companion_dob = serializers.DateField(required=False)
    companion_contact_number = serializers.CharField(
        max_length=20, required=False)
    companion_card_number = serializers.CharField(
        max_length=50, required=False)
    relation_with_member = serializers.CharField(
        max_length=100, required=False)
    companion_image = serializers.ImageField(required=False)
    id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['companion_image'].required = False

    def validate_member_ID(self, value):

        is_exist = Member.objects.filter(member_ID=value).exists()
        if not is_exist:
            raise serializers.ValidationError(
                f"{value} is not a valid member id")
        return value

    def create(self, validated_data):
        member_ID = validated_data.pop("member_ID")
        member = Member.objects.get(member_ID=member_ID)
        instance = CompanionInformation.objects.create(
            **validated_data, member=member)
        return instance

    def update(self, instance, validated_data):
        id = validated_data.get("id")
        if id is not None:
            companion_info = instance
            companion_info.companion_name = validated_data.get(
                "companion_name", companion_info.companion_name)
            companion_info.companion_image = validated_data.get(
                "companion_image", companion_info.companion_image)
            companion_info.companion_dob = validated_data.get(
                "companion_dob", companion_info.companion_dob)
            companion_info.companion_contact_number = validated_data.get(
                "companion_contact_number", companion_info.companion_contact_number)
            companion_info.companion_card_number = validated_data.get(
                "companion_card_number", companion_info.companion_card_number)
            companion_info.relation_with_member = validated_data.get(
                "relation_with_member", companion_info.relation_with_member)
            companion_info.is_active = validated_data.get(
                "is_active", companion_info.is_active)
            companion_info.save(update_fields=["companion_name", "companion_image", "companion_dob",
                                "companion_contact_number", "companion_card_number", "relation_with_member", "is_active"])
            return companion_info
        return instance


class MemberDocumentSerializer(serializers.Serializer):
    member_ID = serializers.CharField()
    document_document = serializers.FileField()
    document_type = serializers.PrimaryKeyRelatedField(
        queryset=DocumentTypeChoice.objects.all())
    document_number = serializers.CharField(max_length=50, required=False)
    id = serializers.IntegerField(required=False)
    is_active = serializers.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['document_document'].required = False

    def validate_member_ID(self, value):

        if not Member.objects.filter(member_ID=value).exists():
            raise serializers.ValidationError(
                f"No member exists with this {value} id")

        return value

    def create(self, validated_data):
        member_ID = validated_data.pop("member_ID")
        member = Member.objects.get(member_ID=member_ID)
        instance = Documents.objects.create(
            **validated_data, member=member)
        return instance

    def update(self, instance, validated_data):
        id = validated_data.get("id")
        if id is not None:
            document_obj = instance
            document_obj.document_document = validated_data.get(
                "document_document", document_obj.document_document)
            document_obj.document_type = validated_data.get(
                "document_type", document_obj.document_type)
            document_obj.document_number = validated_data.get(
                "document_number", document_obj.document_number)
            document_obj.is_active = validated_data.get(
                "is_active", document_obj.is_active)
            document_obj.save(update_fields=[
                              "document_document", "document_type", "document_number", "is_active"])
            return document_obj
        else:
            member_ID = validated_data.pop("member_ID")
            if Member.objects.filter(member_ID=member_ID).exists():
                raise serializers.ValidationError(
                    "No member exists with this id")
            member = Member.objects.get(member_ID=member_ID)
            instance = Documents.objects.create(
                **validated_data, member=member)
        return instance


class MemberHistorySerializer(serializers.ModelSerializer):
    member = serializers.CharField(
        source="member.member_ID", read_only=True)

    class Meta:
        model = MemberHistory
        fields = "__all__"


class MemberContactNumberViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactNumber
        exclude = ["member"]
        depth = 1


class MemberEmailAddressViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Email
        exclude = ["member"]
        depth = 1


class MemberAddressViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        exclude = ["member"]
        depth = 1


class MemberSpouseViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Spouse
        exclude = ["member"]


class MemberDescendantsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Descendant
        exclude = ["member"]
        depth = 1


class MemberEmergencyContactViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        exclude = ["member"]
        depth = 1


class MemberCompanionViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanionInformation
        exclude = ["member"]
        depth = 1


class MemberDocumentsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documents
        exclude = ["member"]
        depth = 1


class MemberJobViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profession
        exclude = ["member"]
        depth = 1


class MemberCertificateViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        exclude = ["member"]
        depth = 1


class MemberSpecialDaysViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialDay
        exclude = ["member"]
        depth = 1


class MemberDocumentViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documents
        fields = "__all__"