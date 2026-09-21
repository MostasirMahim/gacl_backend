from rest_framework.views import APIView
from .serializers import *
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from .models import *
from member.utils.utility_functions import generate_member_id
import pdb
from account.utils.permissions_classes import ChoicesPermission
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.core.cache import cache


class MembershipTypeView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = MembershipTypeSerializer(data=data)
        if serializer.is_valid():
            mem_type = serializer.save()
            name = serializer.validated_data["name"]
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Membership type created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(mem_type.id)
                }
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            membership_types = MembershipType.objects.all()
            serializer = MembershipTypeViewSerializer(
                membership_types, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Membership type retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InstituteNameView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = InstituteNameSerializer(data=data)

        if serializer.is_valid():
            inst_name = serializer.save()
            name = serializer.validated_data["name"]
            code = serializer.validated_data["code"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Institute name created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(inst_name.id),
                    "code": code
                }
            },
                status=status.HTTP_201_CREATED)

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            inst_names = InstituteName.objects.all()
            serializer = InstituteNameViewSerializer(inst_names, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Institute names retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenderView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = GenderSerializer(data=data)
        if serializer.is_valid():
            gender = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Gender created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(gender.id)
                }
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            genders = Gender.objects.all()
            serializer = GenderViewSerializer(genders, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Gender retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MembershipStatusChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = MembershipStatusChoiceSerializer(data=data)
        if serializer.is_valid():
            membership_status = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Membership status created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(membership_status.id)
                }
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            membership_status = MembershipStatusChoice.objects.all()
            serializer = MembershipStatusChoiceViewSerializer(
                membership_status, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Membership status retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MaritalStatusChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = MaritalStatusChoiceSerializer(data=data)
        if serializer.is_valid():
            marital_status = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Marital status created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(marital_status.id)
                }
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            marital_status = MaritalStatusChoice.objects.all()
            serializer = MaritalStatusChoiceViewSerializer(
                marital_status, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Marital status retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmploymentTypeChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = EmploymentTypeChoiceSerializer(data=data)
        if serializer.is_valid():
            employment_type = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Employment type created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(employment_type.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            employment_type = EmploymentTypeChoice.objects.all()
            serializer = EmploymentTypeChoiceViewSerializer(
                employment_type, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Employment type retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailTypeChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = EmailTypeChoiceSerializer(data=data)
        if serializer.is_valid():
            email_type = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Email type created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(email_type.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            email_type = EmailTypeChoice.objects.all()
            serializer = EmailTypeChoiceViewSerializer(email_type, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Email type retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactTypeChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = ContactTypeChoiceSerializer(data=data)
        if serializer.is_valid():
            contact_type = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Contact type created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(contact_type.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            contact_type = ContactTypeChoice.objects.all()
            serializer = ContactTypeChoiceViewSerializer(
                contact_type, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Contact type retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AddressTypeChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = AddressTypeChoiceSerializer(data=data)
        if serializer.is_valid():
            address_type = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Address type created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(address_type.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            address_type = AddressTypeChoice.objects.all()
            serializer = AddressTypeChoiceViewSerializer(
                address_type, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Address type retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentTypeChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = DocumentTypeChoiceSerializer(data=data)
        if serializer.is_valid():
            document_type = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Document type created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(document_type.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            document_type = DocumentTypeChoice.objects.all()
            serializer = DocumentTypeChoiceViewSerializer(
                document_type, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Document type retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpouseStatusChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = SpouseStatusChoiceSerializer(data=data)
        if serializer.is_valid():
            spouse_status = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Spouse status created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(spouse_status.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            spouse_status = SpouseStatusChoice.objects.all()
            serializer = SpouseStatusChoiceViewSerializer(
                spouse_status, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Spouse status retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DescendantRelationChoiceView(APIView):

    def get_permissions(self):
        return [ChoicesPermission()]

    def post(self, request):
        data = request.data
        serializer = DescendantRelationChoiceSerializer(data=data)
        if serializer.is_valid():
            descendant_relation = serializer.save()
            name = serializer.validated_data["name"]

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Descendant relation created successfully",
                "status": "success",
                "data": {
                    "name": name,
                    "id": str(descendant_relation.id)
                }
            })

        else:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "Invalid request",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            descendant_relation = DescendantRelationChoice.objects.all()
            serializer = DescendantRelationChoiceViewSerializer(
                descendant_relation, many=True)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Descendant relation retrieve successful",
                "status": "success",
                "data": serializer.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AllChoicesView(APIView):

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [ChoicesPermission()]
    
    def get(self, request):
        try:
            cache_key = "all_choices_cache"
            cached_data = cache.get(cache_key)
            do_serve_cache = request.query_params.get(
                "cache")
            if do_serve_cache == None:
                do_serve_cache = True
            elif do_serve_cache == "false":
                do_serve_cache = False
            else:
                do_serve_cache = True

            if cached_data and do_serve_cache:
                return Response(cached_data, status=status.HTTP_200_OK)

            # models
            gender = Gender.objects.all()
            membership_type = MembershipType.objects.all()
            institute_name = InstituteName.objects.all()
            membership_status = MembershipStatusChoice.objects.all()
            marital_status = MaritalStatusChoice.objects.all()
            employment_type = EmploymentTypeChoice.objects.all()
            email_type = EmailTypeChoice.objects.all()
            contact_type = ContactTypeChoice.objects.all()
            address_type = AddressTypeChoice.objects.all()
            document_type = DocumentTypeChoice.objects.all()
            spouse_status_choice = SpouseStatusChoice.objects.all()
            descendant_relation_choice = DescendantRelationChoice.objects.all()

            # serializers
            gender_serializer = GenderSerializer(gender, many=True)
            membership_type_serializer = MembershipTypeSerializer(
                membership_type, many=True)
            institute_name_serializer = InstituteNameSerializer(
                institute_name, many=True)
            membership_status_serializer = MembershipStatusChoiceSerializer(

                membership_status, many=True)
            marital_status_serializer = MaritalStatusChoiceSerializer(
                marital_status, many=True)
            employment_type_serializer = EmploymentTypeChoiceSerializer(
                employment_type, many=True)
            email_type_serializer = EmailTypeChoiceSerializer(
                email_type, many=True)
            contact_type_serializer = ContactTypeChoiceSerializer(
                contact_type, many=True)
            address_type_serializer = AddressTypeChoiceSerializer(
                address_type, many=True)
            document_type_serializer = DocumentTypeChoiceSerializer(
                document_type, many=True)
            spouse_status_choice_serializer = SpouseStatusChoiceSerializer(
                spouse_status_choice, many=True)
            descendant_relation_choice_serializer = DescendantRelationChoiceSerializer(
                descendant_relation_choice, many=True)
            response_data = {
                "gender": gender_serializer.data,
                "membership_type": membership_type_serializer.data,
                "institute_name": institute_name_serializer.data,
                "membership_status": membership_status_serializer.data,
                "marital_status": marital_status_serializer.data,
                "employment_type": employment_type_serializer.data,
                "email_type": email_type_serializer.data,
                "contact_type": contact_type_serializer.data,
                "address_type": address_type_serializer.data,
                "document_type": document_type_serializer.data,
                "spouse_status_choice": spouse_status_choice_serializer.data,
                "descendant_relation_choice": descendant_relation_choice_serializer.data
            }
            response = Response({
                "code": status.HTTP_200_OK,
                "message": "All choices retrieve successful",
                "status": "success",
                "data": response_data
            }, status=200)
            cache.set(cache_key, response_data, 60*60)
            return response

        except Exception as e:
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
