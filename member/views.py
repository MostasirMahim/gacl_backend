
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from . import serializers
from .utils.utility_functions import generate_member_id
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Member, Email, MembersFinancialBasics, InstituteName, Certificate, MemberHistory, CompanionInformation, Documents
from .utils.permission_classes import MemberManagementPermission
import logging
from activity_log.tasks import log_activity_task
from activity_log.utils.functions import request_data_activity_log
from core.models import MembershipType
from datetime import datetime
from django.utils import timezone
from core.utils.pagination import CustomPageNumberPagination
import pandas as pd
from django.http import HttpResponse
from io import BytesIO, StringIO
from xhtml2pdf import pisa
from django.shortcuts import render
from .utils.filters import MemberFilter
from .import models
import pdb
from django.db.models import Prefetch
from .utils.utility_functions import log_request
from .models import Spouse, Profession
from .tasks import delete_member_model_dependencies
from django.core.cache import cache
from django.utils.http import urlencode
from .tasks import delete_members_cache, delete_members_specific_cache
from django.http import Http404
logger = logging.getLogger("myapp")
from .services.member_delete_services import MemberBulkDeleteActionService,MemberSingleDeleteActionService
from django.contrib.auth import get_user_model
from account.models import GroupModel, PermissonModel, AssignGroupPermission
from account.tasks import send_member_credentials_email
from .constants import MEMBER_PERMISSIONS
from .utils.phone import normalize_phone
from .utils.permission_classes import MemberApprovePermission, MemberRejectPermission


class MemberView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        elif self.request.method == "DELETE":
            return [MemberManagementPermission()]
        elif self.request.method == "GET":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            member_serializer = serializers.MemberSerializer(
                data=data, context={"request": request})
            is_member_serializer_valid = member_serializer.is_valid()
            if is_member_serializer_valid:
                with transaction.atomic():
                    member = member_serializer.save()
                    # activity log
                    log_request(request, "Member create", "info",
                                "A new member has been created by the user")
                    MemberHistory.objects.create(start_date=timezone.now(
                    ), stored_member_id=member.member_ID, member=member)
                    # cache delete
                    delete_members_cache.delay()
                    return Response({
                        'code': 201,
                        'status': 'success',
                        'message': "Member created successfully",
                        'data': {
                            'member_ID': member.member_ID,
                        },
                    }, status=status.HTTP_201_CREATED)
            else:
                # Merge errors from both serializers
                # activity log
                log_request(request, "Member creation failed", "info",
                            "user tried to create a member but made an invalid request")
                merged_errors = {**member_serializer.errors}
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member creation failed",
                    "errors": merged_errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as server_error:
            logger.exception(str(server_error))
            # activity log
            log_request(request, "Member creation failed", "info",
                        "user tried to create a member but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(server_error)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_id):
        try:
            member = Member.objects.select_related(
                "membership_type", "gender", "marital_status", "institute_name", "membership_status").get(member_ID=member_id)
            data = request.data
            member_serializer = serializers.MemberSerializer(member, data=data)
            is_member_serializer_valid = member_serializer.is_valid()
            if is_member_serializer_valid:
                with transaction.atomic():
                    member = member_serializer.save()
                    # activity log
                    log_request(request, "Member update success",
                                "info", "user updated a member successfully")
                    # cache delete
                    delete_members_cache.delay()

                    return Response({
                        'code': 200,
                        'status': 'success',
                        'message': "Member updated successfully",
                        'data': {
                            'member_ID': member.member_ID,
                        }
                    }, status=status.HTTP_200_OK)
            else:
                # Merge errors from both serializers
                merged_errors = {**member_serializer.errors}
                # activity log
                log_request(request, "Member update failed", "info",
                            "user tried to update member but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member update failed",
                    "errors": merged_errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Member.DoesNotExist:
            # activity log
            log_request(request, "Member update failed", "info",
                        "user tried to update member but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found",
                "errors": {
                    "member": ["Member not found by this member_ID"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as server_error:
            # activity log
            log_request(request, "Member update failed", "info",
                        "user tried to update member but made an invalid request")
            logger.exception(str(server_error))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(server_error)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    def delete(self, request, member_id):

        try:
            member = Member.objects.only(
                "id", "member_ID", "status").get(member_ID=member_id)
            if member.status == 2:
                # activity log
                log_request(request, "Member delete failed", "info",
                            "user tried to delete member but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member is already deleted",
                }, status=status.HTTP_400_BAD_REQUEST)
            member_ID = member.member_ID
            with transaction.atomic():
                MemberHistory.objects.filter(member=member).update(
                    end_date=timezone.now(),
                    transferred_reason="deleted",
                    transferred=True
                )

                Member.objects.filter(member_ID=member.member_ID).update(
                    member_ID=None,
                    status=2,
                    is_active=False
                )

                delete_member_model_dependencies.delay_on_commit(member.id)

                # activity log
                log_request(request, "Member delete success", "info",
                            "user tried to delete a member and succeeded")
                # cache delete
                delete_members_cache.delay()
                return Response({
                    "code": 204,
                    'message': "member deleted",
                    'status': "success",
                    'data': {
                        'member_ID': member_ID,
                    }
                }, status=status.HTTP_204_NO_CONTENT)

        except Member.DoesNotExist:
            # activity log
            log_request(request, "Member delete failed", "error",
                        "user tried to delete member but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found",
                "errors": {
                    "member": ["Member not found by this member_ID"]
                }
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as server_error:
            logger.exception(str(server_error))
            # activity log
            log_request(request, "Member delete failed", "error",
                        "user tried to delete member but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(server_error)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

   
    def get(self, request, member_id):
        try:
            cache_key = f"specific_member::{member_id}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            member = Member.objects.select_related(
                'marital_status', 'membership_status', 'institute_name',
                'membership_type', 'gender'
            ).prefetch_related(
                "contact_numbers", "emails", "addresses", "spouse", "descendants",
                "professions", "emergency_contacts", "companions", "credentials",
                "certificates", "special_days"
            ).get(member_ID=member_id)

            # check if member status is deleted or not
            if member.status == 2:

                log_request(request, "Member view failed", "warning",
                            "user tried to view a member but made an invalid request")
                return Response({
                    "code": 204,
                    "status": "failed",
                    "message": "Member is already deleted",
                    'errors': {
                        'member_ID': [f"{member_id} member has been deleted"]
                    }
                }, status=status.HTTP_204_NO_CONTENT)

            contact_numbers = member.contact_numbers
            emails = member.emails
            addresses = member.addresses
            spouse = member.spouse
            descendant = member.descendants
            emergency = member.emergency_contacts
            companion = member.companions
            certificate = member.certificates
            documents = member.credentials
            jobs = member.professions
            special_days = member.special_days

            if request.GET.get("download_excel"):
                return self.download_excel_file_for_single_member(member, contact_numbers, emails, addresses, spouse, descendant, emergency, companion, certificate, documents, jobs, special_days)
            if request.GET.get("download_pdf"):
                return self.download_pdf_file_for_single_member(member, contact_numbers, emails, addresses, spouse, descendant, emergency, companion, certificate, documents, jobs, special_days)
            # pass the data to the serializers
            member_serializer = serializers.MemberSerializerForViewSingleMember(
                member)
            contact_serializer = serializers.MemberContactNumberViewSerializer(
                contact_numbers, many=True)
            email_serializer = serializers.MemberEmailAddressViewSerializer(
                emails, many=True)
            address_serializer = serializers.MemberAddressViewSerializer(
                addresses, many=True)
            spouse_serializer = serializers.MemberSpouseViewSerializer(
                spouse, many=True)
            descendant_serializer = serializers.MemberDescendantsViewSerializer(
                descendant, many=True)
            emergency_serializer = serializers.MemberEmergencyContactViewSerializer(
                emergency, many=True)
            companion_serializer = serializers.MemberCompanionViewSerializer(
                companion, many=True)
            documents_serializer = serializers.MemberDocumentsViewSerializer(
                documents, many=True)
            jon_serializer = serializers.MemberJobViewSerializer(
                jobs, many=True)
            certificate_serialzier = serializers.MemberCertificateViewSerializer(
                certificate, many=True)
            special_days_serializer = serializers.MemberSpecialDaysViewSerializer(
                special_days, many=True)
            # unwrap the data to make a single object using two serializers data
            data = {
                'member_info': member_serializer.data,
                'contact_info': contact_serializer.data,
                'email_address': email_serializer.data,
                'address': address_serializer.data,
                'job': jon_serializer.data,
                'spouse': spouse_serializer.data,
                'descendant': descendant_serializer.data,
                'emergency_contact': emergency_serializer.data,
                'certificate': certificate_serialzier.data,
                'companion': companion_serializer.data,
                'document': documents_serializer.data,
                'special_days': special_days_serializer.data,
            }
            # activity log
            log_request(request, "Member view successfully", "info",
                        "user tried to view a member and succeeded")
            final_response = Response({
                "code": 200,
                "status": "success",
                "message": f"View member information for member {member_id}",
                'data': data
            }, status=status.HTTP_200_OK)
            # cache response
            cache.set(cache_key, final_response.data, 60*30)
            return final_response

        except Member.DoesNotExist:
            # activity log
            log_request(request, "Member view failed", "error",
                        "user tried to view a member but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found",
                "errors": {
                    "member": ["Member not found by this member_ID"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as server_error:
            logger.exception(str(server_error))
            # activity log
            log_request(request, "Member view failed", "error",
                        "user tried to view a member but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(server_error)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def remove_time_conflicts_from_data(self, df):
        return df.apply(
            lambda col: col.dt.tz_localize(None) if pd.api.types.is_datetime64_any_dtype(
                col) and getattr(col.dtype, 'tz', None) else col
        )

    def write_to_excel_file(self, data, writer, sheet_name):
        df = pd.DataFrame(data)
        df = self.remove_time_conflicts_from_data(df)
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    def download_excel_file_for_single_member(self, member, contact_numbers, emails, addresses, spouse, descendant, emergency, companion, certificate, documents, jobs, special_days):
        member_dict = {
            "id": member.id,
            "member_ID": member.member_ID,
            "first_name": member.first_name,
            "last_name": member.last_name,
            "date_of_birth": member.date_of_birth,
            "batch_number": member.batch_number,
            "anniversary_date": member.anniversary_date,
            "profile_photo": member.profile_photo.url if member.profile_photo else "",
            "blood_group": member.blood_group,
            "nationality": member.nationality,
            "status": member.status,
            "is_active": member.is_active,
            "created_at": member.created_at,
            "updated_at": member.updated_at,
            "gender": member.gender.name,
            "membership_type": member.membership_type.name,
            "institute_name": member.institute_name.name,
            "membership_status": member.membership_status.name,
            "marital_status": member.marital_status.name,
        }
        contact_data = list(contact_numbers.values(
        ).all())
        email_data = list(emails.values().all())
        address_data = list(addresses.values().all())
        spouse_data = list(spouse.values().all())
        descendants_data = list(descendant.values().all())
        emergency_data = list(emergency.values().all())
        companion_data = list(companion.values().all())
        certificate_data = list(certificate.values().all())
        documents_data = list(documents.values().all())
        jobs_data = list(jobs.values().all())
        special_days_data = list(special_days.values().all())

        # Create Excel file in memory
        excel_buffer = BytesIO()
        writer = pd.ExcelWriter(excel_buffer, engine="xlsxwriter")

        # Create "Member Info" sheet (one row DataFrame)
        df_member = pd.DataFrame([member_dict])
        df_member = self.remove_time_conflicts_from_data(df_member)
        df_member.to_excel(writer, index=False, sheet_name="Member Info")

        self.write_to_excel_file(contact_data, writer, "contact numbers")
        self.write_to_excel_file(email_data, writer, "email addresses")
        self.write_to_excel_file(address_data, writer, "addresses")
        self.write_to_excel_file(descendants_data, writer, "descendants")
        self.write_to_excel_file(spouse_data, writer, "spouse")
        self.write_to_excel_file(emergency_data, writer, "emergency contact")
        self.write_to_excel_file(companion_data, writer, "companion")
        self.write_to_excel_file(certificate_data, writer, "certificate")
        self.write_to_excel_file(documents_data, writer, "documents")
        self.write_to_excel_file(jobs_data, writer, "jobs")
        self.write_to_excel_file(special_days_data, writer, "special days")

        writer.close()

        # Create HTTP response with Excel file
        response = HttpResponse(
            excel_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="member_{member.member_ID}_details.xlsx"'
        return response

    def download_pdf_file_for_single_member(self, member, contact_numbers, emails, addresses, spouse, descendant, emergency, companion, certificate, documents, jobs, special_days):
        # TODO: add all context and update the html to pdf file.
        context = {
            "member": member,
            "emails": emails.all(),
            "contacts": contact_numbers.all(),
        }
        # Render HTML template with context
        html_string = render(self.request, "member_pdf.html",
                             context).content.decode("utf-8")
        # Convert HTML to PDF
        pdf_buffer = BytesIO()
        pisa.CreatePDF(StringIO(html_string), dest=pdf_buffer)

        # Return PDF as response
        response = HttpResponse(pdf_buffer.getvalue(),
                                content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename=member_{member.member_ID}.pdf"
        return response


class MemberListView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def get(self, request):
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"members_list::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            # Get all members
            queryset = Member.objects.filter(
                status=0, is_active=True).select_related("membership_type", "institute_name", "membership_status", "marital_status", "gender").order_by("id")

            # Apply filtering only if filters are provided in the request
            if request.GET:  # Check if any query parameters exist
                filterset = MemberFilter(request.GET, queryset=queryset)
                if not filterset.is_valid():
                    # activity log
                    log_request(request, "Member list view failed",
                                "error", "Invalid filters when viewing member list")
                    return Response({
                        "code": 400,
                        "status": "failed",
                        "message": "Invalid filters",
                        "errors": filterset.errors
                    }, status=400)
                queryset = filterset.qs  # Apply filters
                # Check if "download_excel" is in query params
            if request.GET.get("download_excel"):
                return self.export_to_excel(queryset)

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                queryset, request, view=self)

            if paginated_queryset is None:
                paginated_queryset = queryset

            serializer = serializers.MemberSerializer(
                paginated_queryset, many=True)
            # activity log
            log_request(request, "Member list view success",
                        "info", "user viewed member list")
            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "View all members",
                "data": serializer.data
            }, 200)
            cache.set(cache_key, final_response.data, 60*30)
            return final_response

        except Exception as server_error:
            logger.exception(str(server_error))
            # activity log
            log_request(request, "Member list view failed", "error",
                        "user tried to view member list. But made an invalid request")
            return Response({
                'code': 500,
                'status': "failed",
                "message": "An error occurred",
                "errors": {
                    "server_error": [str(server_error)],
                }
            })

    def export_to_excel(self, queryset):
        """Generate Excel file and return as response"""
        # Convert queryset to list of dicts
        data = list(queryset.values(
            "member_ID", "first_name", "last_name", "gender__name",
            "date_of_birth", "batch_number", "anniversary_date",
            "profile_photo", "blood_group", "nationality",
            "membership_type__name", "institute_name__name",
            "membership_status__name", "marital_status__name"
        ))

        # Rename keys to match expected headers
        df = pd.DataFrame(data)
        df.rename(columns={
            "gender__name": "gender",
            "membership_type__name": "membership_type",
            "institute_name__name": "institute_name",
            "membership_status__name": "membership_status",
            "marital_status__name": "marital_status"
        }, inplace=True)
        # Create Excel file in memory
        excel_buffer = BytesIO()
        writer = pd.ExcelWriter(excel_buffer, engine="xlsxwriter")
        df.to_excel(writer, index=False, sheet_name="Members")
        writer.close()

        # Return as downloadable response
        response = HttpResponse(
            excel_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="members.xlsx"'
        return response


class MemberIdView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberIdSerializer(data=data)
            if serializer.is_valid():
                membership_type = serializer.validated_data['membership_type']
                institute_code = serializer.validated_data['institute_name']
                all_id = generate_member_id(membership_type, institute_code)
                # activity log
                log_request(request, "Member id view succeeded", "info",
                            "user tried to view member id and succeeded")
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Generated Member Id successfully",
                    "data": all_id
                }, status=status.HTTP_200_OK)
            else:

                # activity log
                log_request(request, "Member id view failed", "error",
                            "user tried to view member id but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Failed to generate member Id",
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as server_error:
            logger.exception(str(server_error))
            # activity log
            log_request(request, "Member id view failed", "error",
                        "user tried to view member id but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(server_error)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberContactNumberView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [IsAuthenticated(), MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberContactNumberSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()

                # activity log
                log_request(request, "Member contact number added successfully",
                            "info", "user tried to add member contact number and succeeded")

                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member contact number has been created successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_201_CREATED)
            else:
                # activity log
                log_request(request, "Member contact number added failed", "error",
                            "user tried to add member contact number but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member contact number added failed", "error",
                        "user tried to add member contact number but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_ID):
        try:
            member = Member.objects.get(member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberContactNumberSerializer(
                member, data=data)
            if serializer.is_valid():
                instance = serializer.save(instance=member)
                # activity log
                log_request(request, "Member contact number updated successfully",
                            "info", "user tried to update member contact number and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member contact number has been updated successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Member contact number updated failed", "error",
                            "user tried to update member contact number but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except models.Member.DoesNotExist:
            # activity log
            log_request(request, "Member contact number updated failed", "error",
                        "user tried to update member contact number but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member contact number updated failed", "error",
                        "user tried to update member contact number but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, member_ID):
        try:
            member = get_object_or_404(Member, member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberContactNumberDeleteSerializer(
                data=data)
            if serializer.is_valid():
                instance = serializer.validated_data['id']
                instance.delete()

                # activity log
                log_request(request, "Member contact number deleted successfully",
                            "info", "user tried to delete member contact number and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member contact number has been deleted successfully",
                    "status": "success",

                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Member contact number delete failed", "error",
                            "user tried to delete member contact number but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except Http404:
            # activity log
            log_request(request, "Member contact number delete failed", "error",
                        "user tried to delete member contact number but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member contact number delete failed", "error",
                        "user tried to delete member contact number but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberEmailAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberEmailAddressSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()

                # activity log
                log_request(request, "Member email address added successfully",
                            "info", "user tried to add member email address and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member Email address has been created successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_201_CREATED)
            else:
                # activity log
                log_request(request, "Member email address added failed", "error",
                            "user tried to add member email address but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member email address added failed", "error",
                        "user tried to add member email address but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_ID):
        try:

            member = Member.objects.prefetch_related(
                Prefetch(
                    'emails',
                    queryset=Email.objects.select_related('email_type')
                )
            ).get(member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberEmailAddressSerializer(
                member, data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save(instance=member)
                # activity log
                log_request(request, "Member email address updated successfully",
                            "info", "user tried to update member email address and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member Email address has been updated successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_200_OK)
            else:

                # activity log
                log_request(request, "Member email address updated failed", "error",
                            "user tried to update member email address but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except models.Member.DoesNotExist:
            # activity log
            log_request(request, "Member email address updated failed", "error",
                        "user tried to update member email address but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member email address updated failed", "error",
                        "user tried to update member email address but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, member_ID):
        try:
            member = get_object_or_404(Member, member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberEmailAddressDeleteSerializer(
                data=data)
            if serializer.is_valid():
                instance = serializer.validated_data['id']
                print(instance)
                instance.delete()
                # activity log
                log_request(request, "Member email address deleted successfully",
                            "info", "user tried to delete member email address and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member Email address has been deleted successfully",
                    "status": "success"
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Member email address delete failed", "error",
                            "user tried to delete member email address but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            # activity log
            log_request(request, "Member email address delete failed", "error",
                        "user tried to delete member email address but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member email address delete failed", "error",
                        "user tried to delete member email address but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberAddressView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberAddressSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()
                # activity log
                log_request(request, "Member address added successfully",
                            "info", "user tried to add member address and succeeded")

                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member address has been created successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_201_CREATED)
            else:
                # activity log
                log_request(request, "Member address added failed", "error",
                            "user tried to add member address but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member address added failed", "error",
                        "user tried to add member address but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_ID):
        try:
            member = models.Member.objects.get(member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberAddressSerializer(member, data=data)
            if serializer.is_valid():
                instance = serializer.save()
                # activity log
                log_request(request, "Member address updated successfully",
                            "info", "user tried to update member address and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member address has been updated successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_200_OK)
            else:

                # activity log
                log_request(request, "Member address updated failed", "error",
                            "user tried to update member address but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except models.Member.DoesNotExist:

            # activity log
            log_request(request, "Member address updated failed", "error",
                        "user tried to update member address but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member address updated failed", "error",
                        "user tried to update member address but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, member_ID):
        try:
            member = get_object_or_404(Member, member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberAddressDeleteSerializer(data=data)
            if serializer.is_valid():
                instance = serializer.validated_data['id']
                instance.delete()
                # activity log
                log_request(request, "Member address deleted successfully",
                            "info", "user tried to delete member address and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member address has been deleted successfully",
                    "status": "success"
                }, status=status.HTTP_200_OK)
            else:

                # activity log
                log_request(request, "Member address deletion failed", "error",
                            "user tried to delete member address but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except Http404:

            # activity log
            log_request(request, "Member address deletion failed", "error",
                        "user tried to delete member address but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member address deletion failed", "error",
                        "user tried to delete member address but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberSpouseView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberSpouseSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()
                # activity log
                log_request(request, "Member spouse added successfully",
                            "info", "user tried to add member spouse and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member address has been created successfully",
                    "status": "success",
                    "data": {
                        "spouse_id": instance.id
                    }
                }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member spouse added failed", "error",
                            "user tried to add member spouse but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member spouse added failed", "error",
                        "user tried to add member spouse but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        try:
            data = request.data
            id = data.get('id')
            instance = None
            if id:
                try:
                    instance = models.Spouse.objects.get(pk=id)
                except models.Spouse.DoesNotExist:

                    # activity log
                    log_request(request, "Member spouse updated failed", "error",
                                "user tried to update member spouse but made an invalid request")
                    return Response({
                        "code": 404,
                        "status": "failed",
                        "message": "Member spouse does not exist for this id",
                        "errors": {
                            "spouse_id": ["Member spouse does not exist"]
                        }
                    }, status=status.HTTP_404_NOT_FOUND)
            if instance:
                serializer = serializers.MemberSpouseSerializer(
                    instance, data=data)
            else:
                serializer = serializers.MemberSpouseSerializer(data=data)

            if serializer.is_valid():
                with transaction.atomic():
                    if instance is not None:
                        instance = serializer.save(instance=instance)
                        member_ID = serializer.validated_data.get("member_ID")
                        # activity log
                        log_request(request, "Member spouse updated successfully",
                                    "info", "user tried to update member spouse and succeeded")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 200,
                            "message": "Member Spouse has been updated successfully",
                            "status": "success",
                            "data": {
                                "spouse_id": instance.id
                            }
                        }, status=status.HTTP_200_OK)
                    else:

                        instance = serializer.save()
                        member_ID = serializer.validated_data.get("member_ID")
                        # activity log
                        log_request(request, "Member spouse updated successfully",
                                    "info", "user tried to update member spouse and succeeded")

                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 201,
                            "message": "Member spouse has been created successfully",
                            "status": "success",
                            "data": {
                                "spouse_id": instance.id
                            }
                        }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member spouse updated failed", "error",
                            "user tried to update member spouse but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member spouse updated failed", "error",
                        "user tried to update member spouse but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberSpouseDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request, pk):
        try:
            data = request.data
            member_ID = data.get("member_ID")
            spouse = models.Spouse.objects.filter(pk=pk, member__member_ID=member_ID).first()
            if not spouse:
                # activity log
                log_request(request, "Member spouse deleted failed", "error",
                            "user tried to delete member spouse but made an invalid request")
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Member spouse does not exist",
                    "errors": {
                        "spouse_id": ["Member spouse does not exist"]
                    }
                }, status=status.HTTP_404_NOT_FOUND)
            # delete spouse
            spouse.delete()

            # activity log
            log_request(request, "Member spouse deleted successfully",
                        "info", "user tried to delete member spouse and succeeded")
            delete_members_specific_cache.delay(member_ID)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Member spouse deleted successfully"
            }, status=status.HTTP_200_OK)
         
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member spouse deleted failed", "error",
                        "user tried to delete member spouse but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberDescendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberDescendantsSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()
                # activity log
                log_request(request, "Member descendants added successfully",
                            "info", "user tried to add member descendants and succeeded")
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member Descendant has been created successfully",
                    "status": "success",
                    "data": {
                        "descendant_id": instance.id
                    }
                }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member descendants added failed", "error",
                            "user tried to add member descendants but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member descendants added failed", "error",
                        "user tried to add member descendants but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):

        try:
            data = request.data
            id = data.get('id')
            instance = None

            if id:
                try:
                    instance = models.Descendant.objects.get(pk=id)
                except models.Descendant.DoesNotExist:

                    # activity log
                    log_request(request, "Member descendants updated failed", "error",
                                "user tried to update member descendants but made an invalid request")
                    return Response({
                        "code": 404,
                        "status": "failed",
                        "message": "Member Descendant does not exist for this id",
                        "errors": {
                            "descendant_id": ["Member Descendant does not exist"]
                        }
                    }, status=status.HTTP_404_NOT_FOUND)

            if instance:
                serializer = serializers.MemberDescendantsSerializer(
                    instance, data=data)
            else:
                serializer = serializers.MemberDescendantsSerializer(data=data)

            if serializer.is_valid():
                with transaction.atomic():
                    if instance is not None:
                        instance = serializer.save(instance=instance)
                        member_ID = serializer.validated_data.get("member_ID")
                        # activity log
                        log_request(request, "Member descendants updated successfully",
                                    "info", "user tried to update member descendants and succeeded")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 200,
                            "message": "Member Descendant has been updated successfully",
                            "status": "success",
                            "data": {
                                "descendant_id": instance.id
                            }
                        }, status=status.HTTP_200_OK)
                    else:
                        instance = serializer.save()
                        member_ID = serializer.validated_data.get("member_ID")
                        # activity log
                        log_request(request, "Member descendants created successfully",
                                    "info", "user tried to create member descendants and succeeded")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 201,
                            "message": "Member Descendant has been created successfully",
                            "status": "success",
                            "data": {
                                "descendant_id": instance.id
                            }
                        }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member descendants updated failed", "error",
                            "user tried to update member descendants but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member descendants updated failed", "error",
                        "user tried to update member descendants but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberDescendantsDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request, pk):
        try:
            data = request.data
            member_ID = data.get("member_ID")
            descendant = models.Descendant.objects.filter(pk=pk, member__member_ID=member_ID).first()
            if not descendant:
                # activity log
                log_request(request, "Member descendant deleted failed", "error",
                            "user tried to delete member descendant but made an invalid request")
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Member descendant does not exist",
                    "errors": {
                        "descendant_id": ["Member descendant does not exist"]
                    }
                }, status=status.HTTP_404_NOT_FOUND)
            # delete descendant
            descendant.delete()

            # activity log
            log_request(request, "Member descendant deleted successfully",
                        "info", "user tried to delete member descendant and succeeded")
            delete_members_specific_cache.delay(member_ID)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Member descendant deleted successfully"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member descendant deleted failed", "error",
                        "user tried to delete member descendant but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberJobSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()
                # activity log
                log_request(request, "Member job created successfully",
                            "info", "user tried to create member job and succeeded")

                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member job has been created successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member job created failed", "error",
                            "user tried to create member job but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member job created failed", "error",
                        "user tried to create member job but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_ID):
        try:
            member = models.Member.objects.get(member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberJobSerializer(member, data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save(instance=member)
                # activity log
                log_request(request, "Member job updated successfully",
                            "info", "user tried to update member job and succeeded")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member job has been updated successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Member job updated failed", "error",
                            "user tried to update member job but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except models.Member.DoesNotExist:

            # activity log
            log_request(request, "Member job updated failed", "error",
                        "user tried to update member job but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member job updated failed", "error",
                        "user tried to update member job but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, member_ID):
        try:
            member = get_object_or_404(Member, member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberJobDeleteSerializer(data=data)
            if serializer.is_valid():
                instance = serializer.validated_data['id']
                instance.delete()
                # activity log
                log_request(request, "Member job deleted successfully",
                            "info", "user tried to delete member job and succeeded")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member job has been deleted successfully",
                    "status": "success"
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Member job delete failed", "error",
                            "user tried to delete member job but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Http404:

            # activity log
            log_request(request, "Member job delete failed", "error",
                        "user tried to delete member job but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member job delete failed", "error",
                        "user tried to delete member job but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberEmergencyContactView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberEmergencyContactSerializer(
                data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()
                # activity log
                log_request(request, "Member emergency contact created successfully",
                            "info", "user tried to create member emergency contact and succeeded")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member Emergency contact has been created successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member emergency contact created failed", "error",
                            "user tried to create member emergency contact but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member emergency contact created failed", "error",
                        "user tried to create member emergency contact but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_ID):
        try:
            member = models.Member.objects.get(member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberEmergencyContactSerializer(
                member, data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save(instance=member)
                # activity log
                log_request(request, "Member emergency contact updated successfully",
                            "info", "user tried to update an emergency contact and succeeded")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member Emergency contact has been updated successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_200_OK)
            else:

                # activity log
                log_request(request, "Member emergency contact updated failed", "error",
                            "user tried to update an emergency contact but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except models.Member.DoesNotExist:

            # activity log
            log_request(request, "Member emergency contact updated failed", "error",
                        "user tried to update an emergency contact but made an invalid request")

            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member emergency contact updated failed", "error",
                        "user tried to update an emergency contact but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, member_ID):
        try:
            member = get_object_or_404(Member, member_ID=member_ID)
            data = request.data
            serializer = serializers.MemberEmergencyContactDeleteSerializer(
                data=data)
            if serializer.is_valid():
                instance = serializer.validated_data['id']
                instance.delete()
                # activity log
                log_request(request, "Member emergency contact deleted successfully",
                            "info", "user tried to delete an emergency contact and succeeded")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member Emergency contact has been deleted successfully",
                    "status": "success",

                }, status=status.HTTP_200_OK)
            else:

                # activity log
                log_request(request, "Member emergency contact deletion failed", "error",
                            "user tried to delete an emergency contact but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Http404:

            # activity log
            log_request(request, "Member emergency contact deletion failed", "error",
                        "user tried to delete an emergency contact but made an invalid request")

            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member does not exist",
                "errors": {
                    "member": ["Member does not exist"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member emergency contact deletion failed", "error",
                        "user tried to delete an emergency contact but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberCompanionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberCompanionInformationSerializer(
                data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                with transaction.atomic():
                    instance = serializer.save()

                # activity log
                log_request(request, "Member companion created successfully",
                            "info", "user tried to create member companion and succeeded")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "message": "Member Companion has been created successfully",
                    "status": "success",
                    "data": {
                        "companion_id": instance.id
                    }
                }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member companion created failed", "error",
                            "user tried to create member companion but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member companion created failed", "error",
                        "user tried to create member companion but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        try:
            data = request.data
            id = data.get('id')
            if id:
                instance = models.CompanionInformation.objects.get(pk=id)
                serializer = serializers.MemberCompanionInformationSerializer(
                    instance, data=data)
            else:
                instance = None
                serializer = serializers.MemberCompanionInformationSerializer(
                    data=data)

            if serializer.is_valid():
                with transaction.atomic():
                    if instance is not None:
                        member_ID = serializer.validated_data.get("member_ID")
                        instance = serializer.save()

                        # activity log
                        log_request(request, "Member companion updated successfully",
                                    "info", "user tried to update member companion and succeeded")
                        # delete cache for specific view member details
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 200,
                            "message": "Member companion has been updated successfully",
                            "status": "success",
                            "data": {
                                "companion_id": instance.id
                            }
                        }, status=status.HTTP_200_OK)
                    else:
                        instance = serializer.save()
                        member_ID = serializer.validated_data.get("member_ID")
                        # activity log
                        log_request(request, "Member companion created successfully",
                                    "info", "user tried to create member companion and succeeded")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 201,
                            "message": "Member companion has been created successfully",
                            "status": "success",
                            "data": {
                                "companion_id": instance.id
                            }
                        }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member companion updated failed", "error",
                            "user tried to update member companion but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member companion updated failed", "error",
                        "user tried to update member companion but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MemberCompanionDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request, pk):
        try:
            data = request.data
            member_ID = data.get("member_ID")
            companion = models.CompanionInformation.objects.filter(pk=pk, member__member_ID=member_ID).first()

            if not companion:
                log_request(request, "Member companion deletion failed", "error",
                            "A user tried to delete a member companion but it was not found.")
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Member companion not found",
                    "errors": {
                        "companion_id": ["Member companion does not exist"]
                    }
                }, status=status.HTTP_404_NOT_FOUND)

            companion.delete()
            # activity log
            log_request(request, "Member companion deleted successfully",
                        "info", "A user deleted a member companion successfully.")
            delete_members_specific_cache.delay(member_ID)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Member companion deleted successfully"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            log_request(request, "Member companion deletion failed", "error",
                        "A user tried to delete a member companion but an error occurred.")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MemberDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberDocumentSerializer(
                data=data)
            if serializer.is_valid():
                with transaction.atomic():
                    member_ID = serializer.validated_data.get("member_ID")
                    instance = serializer.save()

                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                # activity log
                log_request(request, "Member documents created successfully",
                            "info", "user tried to create member documents and succeeded")

                return Response({
                    "code": 201,
                    "message": "Member documents has been added successfully",
                    "status": "success",
                    "data": {
                        "document_id": instance.id
                    }
                }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member documents created failed", "error",
                            "user tried to create member documents but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member documents created failed", "error",
                        "user tried to create member documents but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            documents = models.Documents.objects.all()

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                documents, request, view=self)
            serializer = serializers.MemberDocumentViewSerializer(
                paginated_queryset, many=True)

            # activity log
            log_request(request, "Member documents retrieved successfully",
                        "info", "user tried to retrieve member documents and succeeded")
            return paginator.get_paginated_response({
                "code": 200,
                "message": "Member documents retrieved successfully",
                "status": "success",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member documents retrieved failed", "error",
                        "user tried to retrieve member documents but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        try:
            data = request.data
            id = data.get('id')
            if id:
                instance = models.Documents.objects.get(pk=id)
                serializer = serializers.MemberDocumentSerializer(
                    instance, data=data)

            else:
                instance = None
                serializer = serializers.MemberDocumentSerializer(data=data)

            if serializer.is_valid():
                with transaction.atomic():
                    if instance is not None:
                        member_ID = serializer.validated_data.get("member_ID")
                        instance = serializer.save(instance=instance)
                        # delete cache for specific view member details
                        delete_members_specific_cache.delay(member_ID)
                        # activity log
                        log_request(request, "Member documents updated successfully",
                                    "info", "user tried to update member documents and succeeded")
                        return Response({
                            "code": 200,
                            "message": "Member Documents has been updated successfully",
                            "status": "success",
                            "data": {
                                "document_id": instance.id
                            }
                        }, status=status.HTTP_200_OK)
                    else:
                        member_ID = serializer.validated_data.get("member_ID")
                        instance = serializer.save()
                        # activity log
                        log_request(request, "Member documents created successfully",
                                    "info", "user tried to create member documents and succeeded")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 201,
                            "message": "Member Documents has been created successfully",
                            "status": "success",
                            "data": {
                                "document_id": instance.id
                            }
                        }, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "Member documents updated failed", "error",
                            "user tried to update member documents but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member documents updated failed", "error",
                        "user tried to update member documents but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberDocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request, pk):
        try:
            data = request.data
            member_ID = data.get("member_ID")
            document = models.Documents.objects.filter(pk=pk, member__member_ID=member_ID).first()
            if not document:
                log_request(request, "Member document deletion failed", "error",
                            "A user tried to delete a member document but it was not found.")
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Document not found",
                    "errors": {
                        "document": ["Document not found"]
                    }
                }, status=status.HTTP_404_NOT_FOUND)
                # activity log
            # success log for deletion
            document.delete()
            log_request(request, "Member document deleted", "info",
                            "A user has successfully deleted a member document.")
            # delete cache for specific view member details
            delete_members_specific_cache.delay(member_ID)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Document has been deleted successfully"
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Member document deletion failed", "error",
                        "A user tried to delete a member document but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AddMemberIDview(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.AddFlexibleMemberIdSerializer(data=data)
            if serializer.is_valid():
                with transaction.atomic():
                    instance = serializer.save()

                # activity log
                log_request(request, "New member id created", "info",
                            "A user has successfully created a new Member ID.")
                return Response({"code": 201, "status": "success", "message": "New Id has been created"}, status=status.HTTP_201_CREATED)
            else:

                # activity log
                log_request(request, "New member id creation failed", "error",
                            "A user tried to create a new Member ID but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "New member id creation failed", "error",
                        "A user tried to create a new Member ID but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberHistoryView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def get(self, request):
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            # convert dictionary for get query params
            query_dict = dict(query_items)
            cache_key = f"all_member_history::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            history = MemberHistory.objects.all().order_by("-created_at")

            # Now get the values
            start_date = query_dict.get("start_date")
            end_date = query_dict.get("end_date")
            transferred = query_dict.get("transferred")
            # Apply filters if query parameters exist
            if start_date and end_date:
                history = history.filter(
                    start_date__date__gte=start_date, end_date__date__lte=end_date)
            elif start_date:
                history = history.filter(start_date__date__gte=start_date)
            elif end_date:
                history = history.filter(end_date__date__lte=end_date)
            if transferred:
                if transferred == "true":
                    transferred = True
                elif transferred == "false":
                    transferred = False
                if isinstance(transferred, bool):
                    history = history.filter(transferred=transferred)

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                history, request, view=self)
            serializer = serializers.MemberHistorySerializer(
                paginated_queryset, many=True)

            # activity log
            log_request(request, "Viewing all members history", "info",
                        "A user has successfully viewing all members history.")

            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "Viewing all members history",
                "data": serializer.data
            }, 200)

            # Cache the response
            cache.set(cache_key, final_response.data, 60*30)
            return final_response
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Viewing all members history failed", "error",
                        "A user tried to view all members history but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberSingleHistoryView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def get(self, request, member_ID):
        try:
            cache_key = f"specific_member_history::{member_ID}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)
            member_history = MemberHistory.objects.filter(
                stored_member_id=member_ID)
            serializer = serializers.MemberHistorySerializer(
                member_history, many=True)

            # activity log
            log_request(request, "Viewing single member history", "info",
                        "A user has successfully viewing single member history.")

            final_response = Response({
                'code': 200,
                'status': 'success',
                "message": "viewing member history",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

            # Cache the response
            cache.set(cache_key, final_response.data, 60*30)
            return final_response
        except MemberHistory.DoesNotExist:

            # activity log
            log_request(request, "Viewing single member history failed", "error",
                        "A user tried to view single member history but made an invalid request.")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found",
                "errors": {
                    "member": ["Member not found by this member_ID"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Viewing single member history failed", "error",
                        "A user tried to view single member history but made an invalid request.")

            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberSpecialDayView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberSpecialDaySerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instances = serializer.save()
                # activity log
                log_request(request, "Creating new member special days", "info",
                            "A user has successfully created new member special days.")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": " Member Special Days has been created successfully",
                    "data": instances
                }, status=status.HTTP_201_CREATED)

            else:

                # activity log
                log_request(request, "Creating new member special days failed", "error",
                            "A user tried to create new member special days but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Creating new member special days failed", "error",
                        "A user tried to create new member special days but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, member_ID):
        try:
            member = models.Member.objects.get(member_ID=member_ID)

            data = request.data
            serializer = serializers.MemberSpecialDaySerializer(
                member, data=data)
            if serializer.is_valid():
                with transaction.atomic():
                    member_ID = serializer.validated_data.get("member_ID")
                    instance = serializer.save(instance=member)

                # activity log
                log_request(request, "Updating member special days", "info",
                            "A user has successfully updated member special days.")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member special day has been updated successfully",
                    "status": "success",
                    "data": instance
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Updating member special days failed", "error",
                            "A user tried to update member special days but made an invalid request")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member.member_ID)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except models.Member.DoesNotExist:
            # activity log
            log_request(request, "Updating member special days failed", "error",
                        "A user tried to update member special days but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found",
                "errors": {
                    "member": ["Member not found by this member_ID"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Updating member special days failed", "error",
                        "A user tried to update member special days but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, member_ID):
        try:
            member = get_object_or_404(Member, member_ID=member_ID)

            data = request.data
            serializer = serializers.MemberSpecialDayDeleteSerializer(
                data=data)
            if serializer.is_valid():
                instance = serializer.validated_data['id']
                instance.delete()

                # activity log
                log_request(request, "deleted member special days", "info",
                            "A user has successfully deleted member special days.")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 200,
                    "message": "Member special day has been deleted successfully",
                    "status": "success"
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_request(request, "Deleting member special days failed", "error",
                            "A user tried to delete member special days but made an invalid request")
                # delete cache for specific view member details
                delete_members_specific_cache.delay(member.member_ID)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            # activity log
            log_request(request, "Deleting member special days failed", "error",
                        "A user tried to delete member special days but made an invalid request")
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found",
                "errors": {
                    "member": ["Member not found by this member_ID"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Deleting member special days failed", "error",
                        "A user tried to Delete member special days but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [MemberManagementPermission()]
        elif self.request.method == "PATCH":
            return [MemberManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberCertificateSerializer(data=data)

            if serializer.is_valid():
                member_ID = serializer.validated_data.get("member_ID")
                instance = serializer.save()

                # activity log
                log_request(request, "Creating new member certificates", "info",
                            "A user has successfully created new member certificates.")
                # delete cache for specific  member details
                delete_members_specific_cache.delay(member_ID)
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Member Certificate has been created successfully",
                    "data": {"id": instance.id, "title": instance.title}
                }, status=status.HTTP_201_CREATED)

            else:

                # activity log
                log_request(request, "Creating new member certificates failed", "error",
                            "A user tried to create new member certificates but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Creating new member certificates failed", "error",
                        "A user tried to create new member certificates but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        try:
            data = request.data
            id = data.get('id')
            if id:
                instance = Certificate.objects.select_related(
                    'member').get(pk=id)

                serializer = serializers.MemberCertificateSerializer(
                    instance, data=data)
            else:
                instance = None
                serializer = serializers.MemberCertificateSerializer(data=data)

            if serializer.is_valid():
                with transaction.atomic():
                    if instance is not None:
                        member_ID = serializer.validated_data.get("member_ID")
                        instance = serializer.save(instance=instance)
                        # activity log
                        log_request(request, "Updating member certificates", "info",
                                    "A user has successfully updated member certificates.")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 200,
                            "message": "Member Certificate has been updated successfully",
                            "status": "success",
                            "data": {
                                "certificate_id": instance.id
                            }
                        }, status=status.HTTP_200_OK)
                    else:
                        member_ID = serializer.validated_data.get("member_ID")
                        instance = serializer.save()
                        # activity log
                        log_request(request, "Creating new member certificates", "info",
                                    "A user has successfully created new member certificates.")
                        delete_members_specific_cache.delay(member_ID)
                        return Response({
                            "code": 201,
                            "message": "Member Certificate has been created successfully",
                            "status": "success",
                            "data": {
                                "certificate_id": instance.id
                            }
                        }, status=status.HTTP_201_CREATED)
            else:
                # activity log
                log_request(request, "Updating member certificates failed", "error",
                            "A user tried to update member certificates but made an invalid request")
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))

            # activity log
            log_request(request, "Updating member certificates failed", "error",
                        "A user tried to update member certificates but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
class MemberCertificateDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request, pk):
        try:
            data = request.data
            member_ID = data.get('member_ID')
            certificate = Certificate.objects.filter(pk=pk, member__member_ID=member_ID).first()

            if not certificate:
                log_request(request, "Member certificate deletion failed", "error",
                            "A user tried to delete a member certificate but it was not found.")
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Certificate not found",
                    "errors": {
                        "certificate": ["Certificate not found by this ID"]
                    }
                }, status=status.HTTP_404_NOT_FOUND)

            certificate.delete()
            # activity log
            log_request(request, "Member certificate deleted", "info",
                        "A user has successfully deleted a member certificate.")
            # delete cache for specific view member details
            delete_members_specific_cache.delay(member_ID)
            return Response({
                "code": 200,
                "status": "success",
                "message": "Certificate deleted successfully"
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Member certificate deletion failed", "error",
                        "A user tried to delete a member certificate but an error occurred.")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class MemberIDListView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def get(self, request):
        try:
            # Get all member IDs for active members
            member_ids = Member.objects.filter(
                status=0, is_active=True
            ).values_list("member_ID", flat=True)
            # activity log
            log_request(request, "Retrieved member ID list", "info",
                        "A user has successfully retrieved the list of member IDs.")

            return Response({
                "code": 200,
                "status": "success",
                "message": "List of all member IDs",
                "data": list(member_ids)
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Retrieved member ID list failed", "error",
                        "A user tried to retrieve the list of member IDs but an error occurred.")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteMemberListView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request):
        try:
            # Query params
            soft_delete_all = request.query_params.get("soft_delete_all", "False").lower() == "true"
            hard_delete_all = request.query_params.get("hard_delete_all", "False").lower() == "true"
            list_of_soft_delete = request.query_params.get("list_of_soft_delete", "False").lower() == "true"
            list_of_hard_delete = request.query_params.get("list_of_hard_delete", "False").lower() == "true"
            list_of_restore = request.query_params.get("list_of_restore", "False").lower() == "true"

            actions = [soft_delete_all, hard_delete_all, list_of_soft_delete, list_of_hard_delete, list_of_restore]
            if sum(actions) > 1:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": {"request": ["Cannot perform multiple actions simultaneously."]}
                }, status=status.HTTP_400_BAD_REQUEST)

            if not any(actions):
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": {"request": ["Please specify at least one action."]}
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get members queryset
            if soft_delete_all or hard_delete_all:
                members = Member.objects.exclude(status=2)  # exclude already deleted
            else:
                member_ids = request.data.get("member_ids", [])
                if not member_ids:
                    return Response({
                        "code": 400,
                        "status": "failed",
                        "message": "No member IDs provided for the list action",
                    }, status=status.HTTP_400_BAD_REQUEST)
                members = Member.objects.filter(member_ID__in=member_ids)

            if not members.exists():
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "No members found to perform this action",
                }, status=status.HTTP_404_NOT_FOUND)

            service = MemberBulkDeleteActionService(request, members)

            if hard_delete_all or list_of_hard_delete:
                result = service.hard_delete()
            elif soft_delete_all or list_of_soft_delete:
                result = service.soft_delete()
            else:
                result = service.restore()

            return Response({
                "code": result['status_code'],
                "status": "success",
                "message": result['message'],
                "data": {"member_IDs": result['member_IDs']}
            }, status=result['status_code'])

        except Exception as e:
            logger.exception(str(e))
            log_request(request, "Delete member IDs failed", "error",
                        "A user tried to delete the list of member IDs but an error occurred.")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
class DeletedMemberListView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def get(self, request):
        try:
            
            members = Member.objects.filter(status=2,is_active=False).order_by("-created_at")

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                members, request, view=self)
            serializer = serializers.MemberSerializer(
                paginated_queryset, many=True)

            # activity log
            log_request(request, "Viewing all deleted members", "info",
                        "A user has successfully viewing all deleted members.")

            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "Viewing all deleted members",
                "data": serializer.data
            }, 200)

            # Cache the response
            return final_response
        except Exception as e:
            logger.exception(str(e))
            # activity log
            log_request(request, "Viewing all deleted members failed", "error",
                        "A user tried to view all deleted members but made an invalid request")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            


class MembersBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request):
        try:
            members = Member.objects.filter(status=2, is_active=False)

            if not members.exists():
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "No deleted members found to permanently delete",
                    "data": {"members": []}
                }, status=status.HTTP_404_NOT_FOUND)

            service = MemberBulkDeleteActionService(request, members)
            result = service.hard_delete()

            return Response({
                "code": result['code'],
                "status": result['status'],
                "message": result['message'],
                "data": result.get('data', {})
            }, status=status.HTTP_204_NO_CONTENT if result['code'] == 204 else status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(str(e))
            log_request(request, "Permanently delete all members failed", "error",
                        "A user tried to permanently delete all members but an error occurred.")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
class MemberHardSingleDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberManagementPermission]

    def delete(self, request, pk):
        try:
            member = Member.objects.filter(id=pk, status=2, is_active=False).first()

            if not member:
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Member not found or not in deleted status",
                    "errors": {
                        "member": ["Member not found by this primary key or not in deleted status"]
                    }
                }, status=status.HTTP_404_NOT_FOUND)

            # Service class call
            service = MemberSingleDeleteActionService(request, member)
            result = service.hard_delete()

            return Response(result, status=result["code"])

        except Exception as e:
            logger.exception(str(e))
            log_request(
                request,
                "Permanently delete a member failed",
                "error",
                "A user tried to permanently delete a member but an error occurred."
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApproveMemberView(APIView):
    """
    POST /api/member/v1/members/<int:member_id>/approve/

    Approves a pending Member application: creates the CustomUser login
    account (username = member_ID, password = normalized primary phone
    number, role = MEMBER), links it to the Member, flips
    application_status to "approved", adds the user to the club_member
    group, and emails the new credentials. See master_update.md Part 3.2.

    Note on the URL id: account/protected_urls.py registers this path
    with a numeric (`\\d+`) pattern, so `member_id` here is the Member's
    numeric primary key (consistent with other endpoints like
    hard_delete/<int:pk>/), not the human-readable member_ID string.
    """
    permission_classes = [IsAuthenticated, MemberApprovePermission]

    def post(self, request, member_id):
        try:
            member = Member.objects.filter(id=member_id).first()
            if not member:
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Member not found",
                    "errors": {"member": ["No member with this id exists"]}
                }, status=status.HTTP_404_NOT_FOUND)

            if member.application_status != "pending":
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member is not pending approval",
                    "errors": {
                        "application_status": [
                            f"Member application_status is '{member.application_status}', "
                            "must be 'pending' to approve."
                        ]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            if member.user_id:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member already has a login account",
                    "errors": {"member": ["This member has already been approved."]}
                }, status=status.HTTP_400_BAD_REQUEST)

            primary_email_obj = member.emails.filter(is_primary=True).first()
            if not primary_email_obj:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member has no primary email on file",
                    "errors": {
                        "email": [
                            "A primary email is required to deliver login "
                            "credentials and to support future password resets."
                        ]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            primary_phone_obj = member.contact_numbers.filter(
                is_primary=True).first()
            if not primary_phone_obj or not primary_phone_obj.number:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member has no primary contact number on file",
                    "errors": {
                        "contact_number": [
                            "A primary contact number is required; it becomes "
                            "the member's initial temporary password."
                        ]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            primary_email = primary_email_obj.email
            temp_password = primary_phone_obj.number

            User = get_user_model()
            if User.objects.filter(username=member.member_ID).exists():
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "A login account with this username already exists",
                    "errors": {
                        "member_ID": [
                            f"A CustomUser with username '{member.member_ID}' "
                            "already exists. Resolve this conflict before approving."
                        ]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                user = User.objects.create_user(
                    username=member.member_ID,
                    password=temp_password,
                    email=primary_email,
                    first_name=member.first_name,
                    last_name=member.last_name,
                    role="MEMBER",
                    is_staff=False,
                    is_superuser=False,
                    must_change_password=True,
                )

                member.user = user
                member.application_status = "approved"
                member.save(update_fields=["user", "application_status"])

                group, _ = GroupModel.objects.get_or_create(name="club_member")
                for pname in MEMBER_PERMISSIONS:
                    perm, _ = PermissonModel.objects.get_or_create(name=pname)
                    group.permission.add(perm)
                assign, _ = AssignGroupPermission.objects.get_or_create(user=user)
                assign.group.add(group)

            send_member_credentials_email.delay_on_commit(
                email=primary_email,
                first_name=member.first_name,
                username=member.member_ID,
                temp_password=temp_password,
            )

            log_request(request, "Member approved", "info",
                        f"Member {member.member_ID} was approved and a login account was created")
            delete_members_cache.delay()
            delete_members_specific_cache.delay(member.member_ID)

            return Response({
                "code": 200,
                "status": "success",
                "message": "Member approved and login credentials sent",
                "data": {
                    "member_id": member.id,
                    "member_ID": member.member_ID,
                    "application_status": member.application_status,
                    "username": user.username,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            log_request(request, "Member approval failed", "error",
                        "An error occurred while approving a member")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RejectMemberView(APIView):
    """
    POST /api/member/v1/members/<int:member_id>/reject/

    Sets application_status = "rejected". No CustomUser is created and no
    credential email is sent. See master_update.md Part 3.2.
    """
    permission_classes = [IsAuthenticated, MemberRejectPermission]

    def post(self, request, member_id):
        try:
            member = Member.objects.filter(id=member_id).first()
            if not member:
                return Response({
                    "code": 404,
                    "status": "failed",
                    "message": "Member not found",
                    "errors": {"member": ["No member with this id exists"]}
                }, status=status.HTTP_404_NOT_FOUND)

            if member.application_status != "pending":
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Member is not pending approval",
                    "errors": {
                        "application_status": [
                            f"Member application_status is '{member.application_status}', "
                            "must be 'pending' to reject."
                        ]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            member.application_status = "rejected"
            member.save(update_fields=["application_status"])

            log_request(request, "Member rejected", "info",
                        f"Member {member.member_ID} application was rejected")
            delete_members_cache.delay()
            delete_members_specific_cache.delay(member.member_ID)

            return Response({
                "code": 200,
                "status": "success",
                "message": "Member application rejected",
                "data": {
                    "member_id": member.id,
                    "member_ID": member.member_ID,
                    "application_status": member.application_status,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            log_request(request, "Member rejection failed", "error",
                        "An error occurred while rejecting a member")
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
