from django.db import models
# from django.contrib.auth import get_user_model
from club.models import Club
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
# Extend the user model with custom fields


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("SUPERADMIN", "Superadmin"),
        ("STAFF", "Staff"),
        ("MEMBER", "Member"),
    ]
    # Single source of truth for "what type of user is this". is_staff /
    # is_superuser are kept as-is (Django's admin site needs them) but
    # application/authorization code should read `role` only, not guess
    # from those flags.
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="STAFF")
    # Forces a mandatory password-change screen on first login for
    # members provisioned via ApproveMemberView (temp password = phone
    # number). Reuses the existing ResetPasswordView flow.
    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return self.username

# Store user generated OTPS in the DB


class ForgetPasswordOTP(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    otp = models.IntegerField()
    expire_time = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=100)

    def __str__(self):
        return self.email

    def is_expired(self):
        """Check if the OTP is expired (valid for 5 minutes)"""
        return timezone.now() > self.expire_time + timedelta(minutes=5)

# authorization Model


class PermissonModel(models.Model):
    name = models.CharField(max_length=250, unique=True)

    def __str__(self):
        return self.name


class GroupModel(models.Model):
    name = models.CharField(max_length=250, unique=True)
    permission = models.ManyToManyField(PermissonModel)

    def __str__(self):
        return self.name


class AssignGroupPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             related_name="custom_user", null=True, blank=True)
    group = models.ManyToManyField(GroupModel)

    def __str__(self):
        groups_all = self.group.all()
        group_name = ""
        for grp in groups_all:
            group_name = group_name + f"{grp} "
        return f"{self.user} - {group_name}"


class OTP(models.Model):
    otp = models.IntegerField()
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email


class VerifySuccessfulEmail(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email
