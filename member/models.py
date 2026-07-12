from django.db import models
from django.conf import settings
from core.models import Gender, BLOOD_GROUPS, COUNTRY_CHOICES, MembershipType, InstituteName, MembershipStatusChoice, MaritalStatusChoice, STATUS_CHOICES, ContactTypeChoice, EmailTypeChoice, EmploymentTypeChoice, DocumentTypeChoice, AddressTypeChoice, DescendantRelationChoice, SpouseStatusChoice
from club.models import Club


class Member(models.Model):
    member_ID = models.CharField(
        max_length=200, unique=True, null=True, blank=True)  # mandatory field
    # Login account for member self-service portal (optional; provisioned
    # so a member can log in, place their own orders, pay, and see only
    # their own data). Staff/admin users are NOT members.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="member_profile")
    first_name = models.CharField(
        max_length=200, blank=True, default="")  # mandatory field
    last_name = models.CharField(
        max_length=200, blank=True, default="")  # optional field
    date_of_birth = models.DateField(null=True, blank=True)  # mandatory field
    batch_number = models.CharField(
        max_length=500, default="")  # optional field
    anniversary_date = models.DateField(
        null=True, blank=True)  # optional field
    profile_photo = models.ImageField(
        upload_to='profile_photos/')  # mandatory field
    # choice fields
    blood_group = models.CharField(
        max_length=100, choices=BLOOD_GROUPS, default='UNKNOWN')  # optional field
    nationality = models.CharField(
        max_length=100, choices=COUNTRY_CHOICES, default='XX')  # optional field

    # relations
    gender = models.ForeignKey(Gender, on_delete=models.RESTRICT,
                               related_name="member_gender")  # mandatory field
    membership_type = models.ForeignKey(
        MembershipType, related_name='membership_type_choice', on_delete=models.RESTRICT)  # mandatory field
    institute_name = models.ForeignKey(
        InstituteName, related_name='institute_name_choice', on_delete=models.RESTRICT)  # mandatory field
    membership_status = models.ForeignKey(
        MembershipStatusChoice, related_name='membership_status_choice', on_delete=models.RESTRICT)  # mandatory field
    marital_status = models.ForeignKey(
        MaritalStatusChoice, related_name='marital_status_choice', on_delete=models.RESTRICT)  # mandatory field

    # Workflow state for the member application/approval process. This is
    # independent of `membership_status` above, which represents member
    # *category* (e.g. general/life/honorary) and is left untouched.
    # application_status tracks whether this Member has been reviewed and
    # given a login account yet:
    #   draft    -> just created via the wizard, not yet submitted for review
    #   pending  -> awaiting admin approve/reject
    #   approved -> CustomUser created & linked, member can log in
    #   rejected -> application declined, no CustomUser created
    APPLICATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    application_status = models.CharField(
        max_length=20, choices=APPLICATION_STATUS_CHOICES, default="draft")

    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.first_name


class MembersFinancialBasics(models.Model):
    # optional field
    membership_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    # optional field
    payment_received = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    # optional field
    membership_fee_remaining = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    # optional field
    subscription_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    # optional field
    dues_limit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    initial_payment_doc = models.FileField(
        upload_to='initial_payment_doc/', blank=True, null=True)  # optional field

    # relations
    member = models.ForeignKey(
        Member, related_name='members_financial_basics', on_delete=models.RESTRICT)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name


# Member other information Models


class ContactNumber(models.Model):
    number = models.CharField(max_length=20, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    # Relations
    member = models.ForeignKey(Member, related_name='contact_numbers',
                               on_delete=models.RESTRICT)
    contact_type = models.ForeignKey(
        ContactTypeChoice, related_name='contact_type_choice', on_delete=models.RESTRICT, default=None, null=True, blank=True)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name

    def save(self, *args, **kwargs):
        # Ensure only one primary contact per member
        if self.is_primary:
            # Set other contacts for this member to non-primary
            ContactNumber.objects.filter(
                member=self.member, is_primary=True).update(is_primary=False)
        elif not ContactNumber.objects.filter(member=self.member, is_primary=True).exists():
            # If no primary contact exists, set this one as primary by default
            self.is_primary = True
        super().save(*args, **kwargs)


class Email(models.Model):
    email = models.EmailField(unique=True, max_length=50)
    is_primary = models.BooleanField(default=False)
    # relations
    member = models.ForeignKey(
        Member, related_name='emails', on_delete=models.RESTRICT)
    email_type = models.ForeignKey(
        EmailTypeChoice, related_name='email_type_choice', on_delete=models.RESTRICT, null=True, blank=True, default=None)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name

    def save(self, *args, **kwargs):
        # Ensure only one primary email per user
        if self.is_primary:
            # Set other emails for this user to non-primary
            Email.objects.filter(member=self.member,
                                 is_primary=True).update(is_primary=False)
        elif not Email.objects.filter(member=self.member, is_primary=True).exists():
            # If no primary email exists, set this one as primary by default
            self.is_primary = True
        super().save(*args, **kwargs)


class Address(models.Model):
    title = models.CharField(max_length=100, null=True, blank=True, default="")
    address = models.TextField()
    is_primary = models.BooleanField(default=False)
    member = models.ForeignKey(
        Member, related_name='addresses', on_delete=models.RESTRICT)
    address_type = models.ForeignKey(
        AddressTypeChoice, related_name='address_type_choice', on_delete=models.RESTRICT, null=True, blank=True, default=None)

    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name

    def save(self, *args, **kwargs):
        # Ensure only one primary address per member
        if self.is_primary:
            # Set other addresses for this member to non-primary
            Address.objects.filter(
                member=self.member, is_primary=True).update(is_primary=False)
        elif not Address.objects.filter(member=self.member, is_primary=True).exists():
            # If no primary address exists, set this one as primary by default
            self.is_primary = True
        super().save(*args, **kwargs)


class Spouse(models.Model):
    spouse_name = models.CharField(max_length=100)
    spouse_contact_number = models.CharField(
        max_length=20, blank=True, null=True, default="")
    spouse_dob = models.DateField(blank=True, null=True)
    image = models.ImageField(
        upload_to='spouse_images/', blank=True, null=True, default=None)
    # relations
    member = models.ForeignKey(
        Member, related_name='spouse', on_delete=models.RESTRICT)
    current_status = models.ForeignKey(
        SpouseStatusChoice, related_name='spouse_current_status', on_delete=models.RESTRICT, null=True, blank=True, default=None)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name


class Descendant(models.Model):
    name = models.CharField(max_length=100)
    descendant_contact_number = models.CharField(
        max_length=20, blank=True, null=True, default=None)
    dob = models.DateField(null=True, blank=True)
    image = models.ImageField(
        upload_to='descendant_images/', blank=True, null=True, default=None)
    # relations
    member = models.ForeignKey(
        Member, related_name='descendants', on_delete=models.RESTRICT)
    relation_type = models.ForeignKey(
        DescendantRelationChoice, related_name='descendant_relation_choice', on_delete=models.RESTRICT, blank=True, null=True, default=None)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name


class Profession(models.Model):
    title = models.CharField(max_length=100)
    organization_name = models.CharField(
        max_length=150, blank=True, null=True, default="")
    job_description = models.TextField(blank=True, null=True, default="")
    location = models.CharField(
        max_length=100, blank=True, null=True, default="")
    # relations
    member = models.ForeignKey(
        Member, on_delete=models.RESTRICT, related_name='professions')

    # Record keeping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class EmergencyContact(models.Model):
    contact_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20)
    relation_with_member = models.CharField(
        max_length=50, blank=True, null=True, default="")
    # relations
    member = models.ForeignKey(Member, related_name='emergency_contacts',
                               on_delete=models.RESTRICT)
    # Record keeping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.member.first_name


class CompanionInformation(models.Model):
    companion_name = models.CharField(max_length=100)
    companion_image = models.ImageField(
        upload_to='companion_images/', blank=True, null=True, default=None)
    companion_dob = models.DateField(blank=True, null=True)
    companion_contact_number = models.CharField(
        max_length=20, blank=True, null=True, default="")
    companion_card_number = models.CharField(
        max_length=50, blank=True, null=True, default="")
    relation_with_member = models.CharField(
        max_length=100, blank=True, null=True, default="")
    # relations
    member = models.ForeignKey(
        Member, related_name='companions', on_delete=models.RESTRICT)
    # Record keeping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.member.first_name


class Documents(models.Model):
    document_number = models.CharField(
        max_length=50, blank=True, null=True, unique=True)
    document_document = models.FileField(upload_to='credentials/')
    # relations
    member = models.ForeignKey(
        Member, related_name='credentials', on_delete=models.RESTRICT)
    document_type = models.ForeignKey(
        DocumentTypeChoice, related_name='document_type_choice', on_delete=models.RESTRICT)

    # Record keeping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.member.first_name


class Certificate(models.Model):
    title = models.CharField(max_length=100)
    certificate_number = models.CharField(
        max_length=100, blank=True, null=True, unique=True)
    certificate_document = models.FileField(upload_to='certificates/')
    # Relations
    member = models.ForeignKey(
        Member, related_name='certificates', on_delete=models.RESTRICT)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name


class SpecialDay(models.Model):
    title = models.CharField(max_length=100)
    date = models.DateField(null=True, blank=True)

    # relations
    member = models.ForeignKey(
        Member, related_name='special_days', on_delete=models.RESTRICT)
    # Record keeping
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.member.first_name


class MemberHistory(models.Model):
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    transferred = models.BooleanField(default=False)
    transferred_reason = models.TextField(blank=True, null=True, default="")
    stored_member_id = models.CharField(max_length=200,default="")  # to store old member ID
    # relation
    member = models.ForeignKey(
        Member, related_name="history", on_delete=models.RESTRICT, null=True, blank=True)
    # record keeping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.stored_member_id
