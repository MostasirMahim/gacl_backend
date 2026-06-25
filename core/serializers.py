from rest_framework import serializers
from .models import *


class MembershipTypeSerializer(serializers.Serializer):
    name = serializers.CharField()
    id = serializers.IntegerField(read_only=True, required=False)

    def validate_name(self, value):
        upp_value = value.upper()
        is_exist = MembershipType.objects.filter(name=upp_value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'{value} already exists'
            )
        return upp_value

    def create(self, validated_data):
        name = validated_data.get('name')
        membership_type = MembershipType.objects.create(name=name)
        return membership_type

class MembershipTypeViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipType
        fields = "__all__"
    
class InstituteNameSerializer(serializers.Serializer):
    name = serializers.CharField()
    code = serializers.CharField()
    id = serializers.IntegerField(read_only=True, required=False)

    

    def validate_name(self, value):
        value_capitalize = value.title()
        is_exist = InstituteName.objects.filter(name=value_capitalize).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'{value} already exists'
            )
        return value_capitalize
    def validate_code(self, value):
        value_upper = value.upper()
        is_exist = InstituteName.objects.filter(code=value_upper).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'{value} already exists'
            )
        return value_upper

    def create(self, validated_data):
        institute_name = InstituteName.objects.create(**validated_data)
        return institute_name

class InstituteNameViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstituteName
        fields = "__all__"

class GenderSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    id = serializers.IntegerField(read_only=True, required=False)

    def validate_name(self, value):
        is_exist = Gender.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This gender name {value} already exists'
            )
        return value

    def create(self, validated_data):
        name = validated_data.get('name')
        gender = Gender.objects.create(name=name)
        return gender

class GenderViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gender
        fields = "__all__"


class MembershipStatusChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)

    # System-provided safe choices. Membership status drives core logic
    # (dashboard counts, pending approval, etc.), so it must be restricted
    # to a known, normalized (lowercase) set rather than free text.
    SAFE_STATUSES = ["pending", "active", "inactive", "suspended", "rejected"]

    def validate_name(self, value):
        normalized = (value or "").strip().lower()
        if normalized not in self.SAFE_STATUSES:
            raise serializers.ValidationError(
                "Membership status must be one of: "
                + ", ".join(self.SAFE_STATUSES)
            )
        is_exist = MembershipStatusChoice.objects.filter(
            name__iexact=normalized).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This membership_status name {normalized} already exists'
            )
        return normalized

    def create(self, validated_data):
        name = validated_data.get('name')
        membership_status = MembershipStatusChoice.objects.create(name=name)
        return membership_status
    
class MembershipStatusChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipStatusChoice
        fields = "__all__"

class MaritalStatusChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)

    
    def validate_name(self, value):
        is_exist = MaritalStatusChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This marital_status name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        marital_status = MaritalStatusChoice.objects.create(name=name)
        return marital_status
class MaritalStatusChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaritalStatusChoice
        fields = "__all__"

class EmploymentTypeChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)

    
    def validate_name(self, value):
        is_exist = EmploymentTypeChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This employment_type name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        employment_type = EmploymentTypeChoice.objects.create(name=name)
        return employment_type
    
class EmploymentTypeChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentTypeChoice
        fields = "__all__"

class EmailTypeChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)

    
    def validate_name(self, value):
        is_exist = EmailTypeChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This email_type name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        email_type = EmailTypeChoice.objects.create(name=name)
        return email_type

class EmailTypeChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTypeChoice
        fields = "__all__"

class ContactTypeChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)

    
    def validate_name(self, value):
        is_exist = ContactTypeChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This contact_type name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        contact_type = ContactTypeChoice.objects.create(name=name)
        return contact_type

class ContactTypeChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactTypeChoice
        fields = "__all__"

class AddressTypeChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)
    
    def validate_name(self, value):
        is_exist = AddressTypeChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This address_type name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        address_type = AddressTypeChoice.objects.create(name=name)
        return address_type

class AddressTypeChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddressTypeChoice
        fields = "__all__"

class DocumentTypeChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)
    
    def validate_name(self, value):
        is_exist = DocumentTypeChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This document_type name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        document_type = DocumentTypeChoice.objects.create(name=name)
        return document_type

class DocumentTypeChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTypeChoice
        fields = "__all__"

class SpouseStatusChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)
    
    def validate_name(self, value):
        is_exist = SpouseStatusChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This spouse_status name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        spouse_status = SpouseStatusChoice.objects.create(name=name)
        return spouse_status

class SpouseStatusChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpouseStatusChoice
        fields = "__all__"

class DescendantRelationChoiceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    id = serializers.IntegerField(read_only=True, required=False)
    
    
    def validate_name(self, value):
        is_exist = DescendantRelationChoice.objects.filter(name=value).exists()
        if is_exist:
            raise serializers.ValidationError(
                f'This descendant_relation name {value} already exists'
            )
        return value
    def create(self, validated_data):
        name = validated_data.get('name')
        descendant_relation = DescendantRelationChoice.objects.create(name=name)
        return descendant_relation

class DescendantRelationChoiceViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = DescendantRelationChoice
        fields = "__all__"
