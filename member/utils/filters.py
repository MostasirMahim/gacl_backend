import django_filters
from ..models import *
from django.db.models import Q, Value
from django.db.models.functions import Concat
import pycountry
import pdb

country_code = [country.name
                for country in pycountry.countries]


class MemberFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_universal_search', label='search')
    q = django_filters.CharFilter(method='filter_universal_search', label='q')
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
    application_status = django_filters.ChoiceFilter(
        choices=Member.APPLICATION_STATUS_CHOICES)

    class Meta:
        model = Member
        fields = [
            "search", "q", "name", "member_ID", 'date_of_birth', 'blood_group', 'nationality',
            'gender', 'membership_type', 'institute_name', 'membership_status',
            'marital_status', 'application_status'
        ]

    def filter_universal_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        tokens = val.split()
        if not tokens:
            return queryset

        # Annotate full name so queries like "Sandra Medina" match seamlessly
        annotated_qs = queryset.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name')
        )

        for token in tokens:
            annotated_qs = annotated_qs.filter(
                Q(full_name__icontains=token) |
                Q(member_ID__icontains=token) |
                Q(emails__email__icontains=token) |
                Q(contact_numbers__number__icontains=token) |
                Q(membership_type__name__icontains=token) |
                Q(membership_status__name__icontains=token) |
                Q(institute_name__name__icontains=token) |
                Q(user__username__icontains=token) |
                Q(batch_number__icontains=token)
            )
        return annotated_qs.distinct()

    def filter_name(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        tokens = val.split()
        if not tokens:
            return queryset

        annotated_qs = queryset.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name')
        )
        for token in tokens:
            annotated_qs = annotated_qs.filter(
                Q(full_name__icontains=token) |
                Q(member_ID__icontains=token)
            )
        return annotated_qs.distinct()

    def filter_email(self, queryset, name, value):
        return queryset.filter(emails__email__icontains=value).distinct()

    def filter_contact_number(self, queryset, name, value):
        return queryset.filter(contact_numbers__number__icontains=value).distinct()
