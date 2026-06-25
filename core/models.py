from django.db import models
import pycountry
from django.contrib.auth import get_user_model
from club.models import Club


User = get_user_model()

STATUS_CHOICES = [
    (0, 'Active'),
    (1, 'Inactive'),
    (2, 'Deleted'),
]


class Gender(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


BLOOD_GROUPS = [
    ('A+', 'A+'),
    ('A-', 'A-'),
    ('B+', 'B+'),
    ('B-', 'B-'),
    ('AB+', 'AB+'),
    ('AB-', 'AB-'),
    ('O+', 'O+'),
    ('O-', 'O-'),
    ('UNKNOWN', 'UNKNOWN')
]

# Country choices generated from pycountry
COUNTRY_CHOICES = [(country.alpha_2, country.name)
                   for country in pycountry.countries]
COUNTRY_CHOICES.append(('XX', 'Unknown'))


#### MEMBER choices ####

class MembershipType(models.Model):
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name


class InstituteName(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True, default="", null=True)

    def __str__(self):
        return self.name


class MembershipStatusChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def save(self, *args, **kwargs):
        # Normalize to a safe, lowercase, trimmed value so that
        # "Pending" and "pending" are treated as the same status and
        # never disrupt status-dependent logic (dashboard counts, etc.).
        if self.name:
            self.name = self.name.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class MaritalStatusChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class EmploymentTypeChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class EmailTypeChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class ContactTypeChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class AddressTypeChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class DocumentTypeChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class SpouseStatusChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class DescendantRelationChoice(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
