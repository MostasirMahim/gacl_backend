import django_filters
from ..models import *
from django.db.models import Q
import pycountry
import pdb

country_code = [country.name
                for country in pycountry.countries]


class MemberFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(method='filter_name', label='name')
    member_ID = django_filters.CharFilter(
        field_name="member_ID", lookup_expr="icontains")
    date_of_birth = django_filters.DateFilter()
    email = django_filters.CharFilter(method="filter_email", label="email")
    contact_number = django_filters.CharFilter(
        method="filter_contact_number", label="contact_number")
    blood_group = django_filters.CharFilter(
        lookup_expr='icontains')
    nationality = django_filters.CharFilter(
        lookup_expr='icontains')
    # ForeignKey filters (exact match)
    gender = django_filters.ModelChoiceFilter(
        queryset=Gender.objects.all(), to_field_name="name")
    membership_type = django_filters.ModelChoiceFilter(
        queryset=MembershipType.objects.all(), to_field_name="name")
    institute_name = django_filters.ModelChoiceFilter(
        queryset=InstituteName.objects.all(), to_field_name="name")
    membership_status = django_filters.ModelChoiceFilter(
        queryset=MembershipStatusChoice.objects.all(), to_field_name="name")
    marital_status = django_filters.ModelChoiceFilter(
        queryset=MaritalStatusChoice.objects.all(), to_field_name="name")
    # Workflow-state filter, independent of membership_status (category).
    # Needed so the "Pending Members" page can filter on
    # application_status="pending" instead of the old free-text
    # membership_status="pending" hack.
    application_status = django_filters.ChoiceFilter(
        choices=Member.APPLICATION_STATUS_CHOICES)

    class Meta:
        model = Member
        fields = [
            "member_ID", 'date_of_birth', 'blood_group', 'nationality',
            'gender', 'membership_type', 'institute_name', 'membership_status',
            'marital_status', 'application_status'
        ]

    def filter_name(self, queryset, name, value):
        """
        This method filters the queryset by searching both first_name and last_name.
        It performs a case-insensitive partial match.
        """
        return queryset.filter(Q(first_name__icontains=value) | Q(last_name__icontains=value))

    def filter_email(self, queryset, name, value):
        return queryset.filter(emails__email__icontains=value)

    def filter_contact_number(self, queryset, name, value):
        return queryset.filter(emails__email__icontains=value)

    def filter_contact_number(self, queryset, name, value):
        return queryset.filter(contact_numbers__number__icontains=value)
