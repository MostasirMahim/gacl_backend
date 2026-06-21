from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
import logging

from . import serializers
from .models import StaffProfile, RFIDCard, Guest, AttendanceRecord
from .utils.permission_classes import AttendanceManagementPermission
from core.utils.pagination import CustomPageNumberPagination

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class StaffProfileView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [AttendanceManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = StaffProfile.objects.select_related("user").filter(is_active=True)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.StaffProfileSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.StaffProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success",
                            "Staff profile created", data=serializer.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class StaffGuestToggleView(APIView):
    """Admin enables/disables whether a staff member may register guests."""
    permission_classes = [AttendanceManagementPermission]

    def patch(self, request, staff_id):
        try:
            staff = StaffProfile.objects.get(id=staff_id)
        except StaffProfile.DoesNotExist:
            return Response(_envelope(404, "failed", "Staff not found"),
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.StaffGuestToggleSerializer(data=request.data)
        if serializer.is_valid():
            staff.guest_allowed = serializer.validated_data["guest_allowed"]
            staff.save(update_fields=["guest_allowed", "updated_at"])
            return Response(_envelope(200, "success", "Guest permission updated",
                            data={"guest_allowed": staff.guest_allowed}))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class RFIDCardView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [AttendanceManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = RFIDCard.objects.filter(is_active=True)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.RFIDCardSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.RFIDCardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Card registered",
                            data=serializer.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class GuestView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        qs = Guest.objects.filter(is_active=True)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.GuestSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.GuestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Guest registered",
                            data=serializer.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class AttendanceRecordView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        qs = AttendanceRecord.objects.filter(is_active=True)
        subject = request.query_params.get("subject_type")
        if subject:
            qs = qs.filter(subject_type=subject)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.AttendanceRecordSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.AttendanceRecordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Attendance recorded",
                            data=serializer.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class CardScanView(APIView):
    """
    Scan a card UID: if the subject has an open record -> check out,
    otherwise -> check in. Works for member / staff / guest cards.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = serializers.CheckInByCardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors),
                            status=status.HTTP_400_BAD_REQUEST)
        card_uid = serializer.validated_data["card_uid"]
        try:
            card = RFIDCard.objects.get(card_uid=card_uid, is_active=True)
        except RFIDCard.DoesNotExist:
            return Response(_envelope(404, "failed", "Card not recognised"),
                            status=status.HTTP_404_NOT_FOUND)

        subject_type, member, staff, guest = self._resolve_subject(card)
        if subject_type is None:
            return Response(_envelope(400, "failed", "Card is not assigned"),
                            status=status.HTTP_400_BAD_REQUEST)

        open_rec = AttendanceRecord.objects.filter(
            card=card, check_out__isnull=True, is_active=True).first()
        if open_rec:
            open_rec.check_out = timezone.now()
            open_rec.save(update_fields=["check_out", "updated_at"])
            return Response(_envelope(200, "success", "Checked out",
                            data=serializers.AttendanceRecordSerializer(open_rec).data))

        rec = AttendanceRecord.objects.create(
            subject_type=subject_type, member=member, staff=staff,
            guest=guest, card=card, check_in=timezone.now())
        return Response(_envelope(201, "success", "Checked in",
                        data=serializers.AttendanceRecordSerializer(rec).data),
                        status=status.HTTP_201_CREATED)

    def _resolve_subject(self, card):
        if card.card_type == "member" and card.member_id:
            return "member", card.member, None, None
        if card.card_type == "staff" and card.staff_id:
            return "staff", None, card.staff, None
        if card.card_type == "guest_temporary":
            guest = card.guest_assignments.filter(is_active=True).order_by("-id").first()
            if guest:
                return "guest", None, None, guest
        return None, None, None, None
