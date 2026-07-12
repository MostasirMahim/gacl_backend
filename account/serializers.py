from rest_framework import serializers
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework import serializers
from django.contrib.auth import get_user_model
from club.models import Club
from .models import *
from random import randint
import pdb

# user serializes


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        exclude = ["password", "last_login",
                   "is_superuser", "groups", "user_permissions"]
        depth = 1


# Authentication serializers
class RegistrationSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    remember_me = serializers.BooleanField(default=False)

    class Meta:
        model = get_user_model()
        fields = ['username', 'password', 'email',
                  'name', 'remember_me']
        extra_kwargs = {
            "name": {
                "required": True,
            },
            "email": {
                "required": True,
            },
            "username": {
                "required": True,
            },
            "password": {
                "required": True,
            }
        }

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        is_same_email_exists = get_user_model().objects.filter(
            email=email).exists()
        if is_same_email_exists:
            raise serializers.ValidationError({
                'email': f"{email} already exists",
            })
        if len(password) < 6:
            raise serializers.ValidationError({
                'password': f"Password must be at least 6 character. Current length {len(password)}"
            })

        return super().validate(attrs)

    def create(self, validated_data):
        username = validated_data.get('username')
        email = validated_data.get('email')
        password = validated_data.get('password')
        name = validated_data.get('name')

        user = get_user_model().objects.create_user(
            username=username, password=password, email=email, first_name=name)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    remember_me = serializers.BooleanField(default=False)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        user = get_user_model().objects.filter(
            username=username).exists()

        if not user:
            raise serializers.ValidationError({
                'username': [f"user {username} doesn't exist"]
            })

        else:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError({
                    'password': [f"password didn't matched"]
                })

        return super().validate(attrs)


class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs.get("email")
        is_user_exist_with_email = get_user_model().objects.filter(
            email=email).exists()
        if not is_user_exist_with_email:
            raise serializers.ValidationError({
                'email': [f"No user exist with {email}"]
            })
        return super().validate(attrs)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        is_user_exist = get_user_model().objects.filter(
            email=email).exists()
        if not is_user_exist:
            raise serializers.ValidationError({
                'email': [f"No user exist with {email}"]
            })
        if len(password) < 6:
            raise serializers.ValidationError({
                'password': ["Password must be 6 character long"]
            })
        return super().validate(attrs)


class UpdatePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, write_only=True)
    new_password = serializers.CharField(max_length=128, write_only=True)
    confirm_password = serializers.CharField(max_length=128, write_only=True)

    def validate(self, attrs):
        user = self.context.get('user')
        current_password = attrs.get("current_password")
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if not user.check_password(current_password):
            raise serializers.ValidationError(
                {"current_password": ["Invalid current password"]})
        if current_password == new_password:
            raise serializers.ValidationError({"current_password": [
                                              "current password and new password are same.please choose a different password"]})

        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match"]})

        if len(new_password) < 6:
            raise serializers.ValidationError(
                {"new_password": ["Password must be at least 6 characters long"]})

        return attrs

    def update(self, instance, validated_data):
        instance.set_password(validated_data["new_password"])
        # A password change via this authenticated flow satisfies the
        # mandatory "set a new password" requirement for freshly-approved
        # member accounts (ApproveMemberView sets this True on create).
        instance.must_change_password = False
        instance.save()
        return instance


class VerifyOtpSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    email = serializers.EmailField()


# autherzaiton serializers


class CustomPermissionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)

    def validate_name(self, value):
        restricted_words = ["admin", "user"]
        if any(word in value.lower() for word in restricted_words):
            raise serializers.ValidationError(
                "The name cannot contain 'admin' or 'user'.")

        if PermissonModel.objects.filter(name=value.replace(' ', '_').lower()).exists():
            raise serializers.ValidationError(
                f"Permission with this name {value} already exists.")

        return value

    def create(self, validated_data):
        name = validated_data.get('name')
        permission = PermissonModel.objects.create(
            name=name.replace(' ', '_').lower())

        return permission


class CustomPermissionSerializerForView(serializers.ModelSerializer):
    class Meta:
        model = PermissonModel
        fields = "__all__"


class GroupModelSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=250, required=True)
    permission = serializers.PrimaryKeyRelatedField(
        queryset=PermissonModel.objects.all(), many=True, required=True)

    def validate_name(self, value):
        if self.instance:
            # if we are updating existing instance then make sure new name doesn't conflict with existing groups
            if self.instance.name != value:
                is_new_name_exist = GroupModel.objects.filter(
                    name=value).exists()
                if is_new_name_exist:
                    raise serializers.ValidationError(
                        f"{value} name already exists")

            return value
        name = value.replace(' ', '_').lower()
        if GroupModel.objects.filter(name=name).exists():
            raise serializers.ValidationError(
                f"Group with this name {value} already exists.")

        return name

    def create(self, validated_data):

        permissions_data = validated_data.pop('permission')
        group = GroupModel.objects.create(**validated_data)
        group.permission.set(permissions_data)
        return group

    def update(self, instance, validated_data):
        group_name = validated_data.get("name")
        permissions = validated_data.get("permission")
        instance.name = group_name
        instance.permission.set(permissions)
        instance.save()
        return instance


class GroupModelSerializerV2(serializers.Serializer):
    name = serializers.CharField(max_length=250, required=False)
    permission = serializers.PrimaryKeyRelatedField(
        queryset=PermissonModel.objects.all(), many=True, required=False)

    def validate_name(self, value):
        if self.instance:
            # if we are updating existing instance then make sure new name doesn't conflict with existing groups
            if self.instance.name != value:
                is_new_name_exist = GroupModel.objects.filter(
                    name=value).exists()
                if is_new_name_exist:
                    raise serializers.ValidationError(
                        f"{value} name already exists")

            return value
        name = value.replace(' ', '_').lower()
        if GroupModel.objects.filter(name=name).exists():
            raise serializers.ValidationError(
                f"Group with this name {value} already exists.")

        return name

    def create(self, validated_data):

        permissions_data = validated_data.pop('permission')
        group = GroupModel.objects.create(**validated_data)
        group.permission.set(permissions_data)
        return group

    def update(self, instance, validated_data):
        group_name = validated_data.get("name", None)
        permissions = validated_data.get("permission", None
                                         )
        if group_name:
            instance.name = group_name
        if permissions:
            for permission in permissions:
                instance.permission.add(permission)
        instance.save()
        return instance


class AssignGroupPermissionSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(), required=True)
    group = serializers.PrimaryKeyRelatedField(
        queryset=GroupModel.objects.all(), many=True, required=True)

    def create(self, validated_data):
        groups = validated_data.pop('group')
        user = validated_data.get("user")
        if AssignGroupPermission.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "Already assigned a group. Please make patch request to update or add to new group.")
        assign_group_permission = AssignGroupPermission.objects.create(
            **validated_data)

        assign_group_permission.group.set(groups)

        return assign_group_permission

    def update(self, instance, validated_data):
        groups = validated_data.get('group', [])
        instance.group.set(groups)
        instance.save()
        return instance


class AssignGroupPermissionSerializerV2(serializers.Serializer):
    users = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(), required=True, many=True)
    group = serializers.PrimaryKeyRelatedField(
        queryset=GroupModel.objects.all(), required=True)

    def create(self, validated_data):
        group = validated_data.pop('group')
        users = validated_data.get("users")
        for user in users:
            assign_obj, _ = AssignGroupPermission.objects.get_or_create(
                user=user)
            if not assign_obj.group.filter(id=group.id).exists():
                assign_obj.group.add(group)
                assign_obj.save()
        return True

    def update(self, instance, validated_data):
        groups = validated_data.get('group', [])
        instance.group.set(groups)
        instance.save()
        return instance


class GroupSerializerForViewAllGroups(serializers.ModelSerializer):
    class Meta:
        model = GroupModel
        fields = "__all__"
        depth = 1


class GroupSerializerForViewAllGroupsV2(serializers.ModelSerializer):
    permission_count = serializers.IntegerField(read_only=True)
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = GroupModel
        fields = ["id", "name", "permission_count", "user_count"]


class DeleteUserFromGroupSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(), required=True)
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=GroupModel.objects.all(), required=True)

    def validate_group_id(self, value):
        user = self.initial_data.get('user_id')
        user = get_user_model().objects.get(pk=user)
        # Check if the user is in the group
        user_in_group = AssignGroupPermission.objects.filter(
            user=user, group=value
        ).exists()
        if not user_in_group:
            raise serializers.ValidationError("The user is not in this group.")

        return value


class AssignGroupPermissionSerializerForView(serializers.Serializer):

    class Meta:
        model = AssignGroupPermission
        fields = "__all__"
        depth = 1


class AdminUserEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        user = get_user_model().objects.filter(email=value).exists()
        if user:
            raise serializers.ValidationError(
                "Email already exists.")
        verified_email = VerifySuccessfulEmail.objects.filter(
            email=value).exists()
        if verified_email:
            VerifySuccessfulEmail.objects.filter(email=value).delete()
        return value

    def create(self, validated_data):
        email = validated_data.get('email')
        otp = randint(1000, 9999)
        is_exists = OTP.objects.filter(email=email).exists()
        if is_exists:
            otp_instance = OTP.objects.get(email=email)
            otp_instance.otp = otp
            otp_instance.save(update_fields=["otp"])
        else:
            otp_instance = OTP.objects.create(email=email, otp=otp)
        return otp_instance


class AdminUserVerifyOtpSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    email = serializers.EmailField()

    def validate(self, attrs):
        otp = attrs.get("otp")
        email = attrs.get("email")
        verified_email = VerifySuccessfulEmail.objects.filter(
            email=email).exists()
        if verified_email:
            raise ValidationError(
                {'email': ["Email already verified."]})

        is_valid = OTP.objects.filter(otp=otp, email=email).exists()
        if not is_valid:
            raise ValidationError(
                {'otp': [f"OTP {otp} and Email {email} do not match previous email and otp"]})
        return super().validate(attrs)


class VerifySuccessfulAllEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class AdminUserRegistrationSerializer(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta:
        model = get_user_model()
        fields = ['username', 'password', 'email',
                  'name']
        extra_kwargs = {
            "name": {
                "required": True,
            },
            "email": {
                "required": True,
            },
            "username": {
                "required": True,
            },
            "password": {
                "required": True,
            }
        }

    def validate(self, attrs):

        email = attrs.get('email')
        password = attrs.get('password')
        is_exist = get_user_model().objects.filter(email=email)
        if is_exist:
            raise ValidationError({"email": ["email already exist"]})

        is_email_exists = VerifySuccessfulEmail.objects.filter(
            email=email).exists()
        if not is_email_exists:
            raise serializers.ValidationError({
                'email': [f"{email} not found in VerifySuccessfulEmail.Please first of all verify user email. "],
            })
        if len(password) < 6:
            raise serializers.ValidationError({
                'password': [f"Password must be at least 6 character. Current length {len(password)}"]
            })

        return super().validate(attrs)

    def create(self, validated_data):
        username = validated_data.get('username')
        email = validated_data.get('email')
        password = validated_data.get('password')
        name = validated_data.get('name')
        user = get_user_model().objects.create_user(
            username=username, password=password, email=email, first_name=name,
            is_staff=True, role="STAFF")
        return user


class GroupDetailsSerializer(serializers.Serializer):
    name = serializers.CharField()
