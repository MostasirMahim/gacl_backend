from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
import csv
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
        # Bug 2.4: search staff by name / staff ID / designation
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(staff_ID__icontains=search) |
                Q(designation__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__username__icontains=search))
        guest_allowed = request.query_params.get("guest_allowed")
        if guest_allowed in ("true", "false"):
            qs = qs.filter(guest_allowed=(guest_allowed == "true"))
        qs = qs.order_by("staff_ID")
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
        qs = RFIDCard.objects.select_related(
            "member", "staff", "staff__user").filter(is_active=True)
        # Bug 2.1: filters for the card list
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(card_uid__icontains=search) |
                Q(member__member_ID__icontains=search) |
                Q(member__first_name__icontains=search) |
                Q(staff__staff_ID__icontains=search))
        card_type = request.query_params.get("card_type")
        if card_type:
            qs = qs.filter(card_type=card_type)
        assigned = request.query_params.get("is_assigned")
        if assigned in ("true", "false"):
            qs = qs.filter(is_assigned=(assigned == "true"))
        qs = qs.order_by("-created_at")
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


class RFIDCardDetailView(APIView):
    """Bug 2.1: deactivate / reassign a single card."""
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [AttendanceManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return RFIDCard.objects.get(id=pk)
        except RFIDCard.DoesNotExist:
            return None

    def get(self, request, pk):
        card = self._get(pk)
        if not card:
            return Response(_envelope(404, "failed", "Card not found"),
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_envelope(200, "success", "Card detail",
                        data=serializers.RFIDCardSerializer(card).data))

    def patch(self, request, pk):
        card = self._get(pk)
        if not card:
            return Response(_envelope(404, "failed", "Card not found"),
                            status=status.HTTP_404_NOT_FOUND)
        # assign / reassign
        serializer = serializers.RFIDCardAssignSerializer(data=request.data)
        if serializer.is_valid():
            d = serializer.validated_data
            card.card_type = d["card_type"]
            card.member_id = d.get("member") if d["card_type"] == "member" else None
            card.staff_id = d.get("staff") if d["card_type"] == "staff" else None
            card.is_assigned = bool(card.member_id or card.staff_id)
            card.save()
            return Response(_envelope(200, "success", "Card updated",
                            data=serializers.RFIDCardSerializer(card).data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # deactivate (soft) the card
        card = self._get(pk)
        if not card:
            return Response(_envelope(404, "failed", "Card not found"),
                            status=status.HTTP_404_NOT_FOUND)
        card.is_active = False
        card.save(update_fields=["is_active", "updated_at"])
        return Response(_envelope(200, "success", "Card deactivated"))


class RFIDCardHistoryView(APIView):
    """Bug 2.1: attendance history for a single card."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        qs = AttendanceRecord.objects.select_related(
            "member", "staff", "staff__user", "guest", "card").filter(
            card_id=pk).order_by("-check_in")
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.AttendanceRecordSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class GuestView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        qs = Guest.objects.select_related(
            "host_member", "host_staff", "host_staff__user",
            "temporary_card").filter(is_active=True)
        # Bug 2.3: search guests
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(host_member__member_ID__icontains=search))
        relation = request.query_params.get("guest_relation")
        if relation:
            qs = qs.filter(guest_relation=relation)
        qs = qs.order_by("-created_at")
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


class GuestDetailView(APIView):
    """Bug 2.3: assign a temporary card to a guest / deactivate guest."""
    def get_permissions(self):
        return [IsAuthenticated()]

    def patch(self, request, pk):
        try:
            guest = Guest.objects.get(id=pk)
        except Guest.DoesNotExist:
            return Response(_envelope(404, "failed", "Guest not found"),
                            status=status.HTTP_404_NOT_FOUND)
        card_id = request.data.get("temporary_card")
        if card_id:
            try:
                card = RFIDCard.objects.get(id=card_id, is_active=True)
            except RFIDCard.DoesNotExist:
                return Response(_envelope(400, "failed",
                                "Card not found"),
                                status=status.HTTP_400_BAD_REQUEST)
            guest.temporary_card = card
            guest.save(update_fields=["temporary_card", "updated_at"])
        return Response(_envelope(200, "success", "Guest updated",
                        data=serializers.GuestSerializer(guest).data))

    def delete(self, request, pk):
        try:
            guest = Guest.objects.get(id=pk)
        except Guest.DoesNotExist:
            return Response(_envelope(404, "failed", "Guest not found"),
                            status=status.HTTP_404_NOT_FOUND)
        guest.is_active = False
        guest.save(update_fields=["is_active", "updated_at"])
        return Response(_envelope(200, "success", "Guest removed"))


def _filter_records(request):
    qs = AttendanceRecord.objects.select_related(
        "member", "staff", "staff__user", "guest", "card").filter(
        is_active=True)
    subject = request.query_params.get("subject_type")
    if subject:
        qs = qs.filter(subject_type=subject)
    # Bug 2.2: search by member name / id
    search = request.query_params.get("search")
    if search:
        qs = qs.filter(
            Q(member__member_ID__icontains=search) |
            Q(member__first_name__icontains=search) |
            Q(member__last_name__icontains=search) |
            Q(staff__staff_ID__icontains=search) |
            Q(guest__name__icontains=search))
    # Bug 2.2: today / period filters
    if request.query_params.get("today") == "true":
        today = timezone.localdate()
        qs = qs.filter(check_in__date=today)
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if date_from:
        d = parse_date(date_from)
        if d:
            qs = qs.filter(check_in__date__gte=d)
    if date_to:
        d = parse_date(date_to)
        if d:
            qs = qs.filter(check_in__date__lte=d)
    return qs.order_by("-check_in")


class AttendanceRecordView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        qs = _filter_records(request)
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


class AttendanceRecordExportView(APIView):
    """Bug 2.2: CSV export of (filtered) attendance records."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _filter_records(request)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="attendance_records.csv"')
        writer = csv.writer(response)
        writer.writerow(["ID", "Type", "Identifier", "Name",
                         "Card UID", "Check In", "Check Out", "Status"])
        for rec in qs:
            ser = serializers.AttendanceRecordSerializer(rec).data
            writer.writerow([
                ser["id"], ser["subject_type"], ser["subject_identifier"],
                ser["subject_name"], ser["card_uid"] or "",
                ser["check_in"], ser["check_out"] or "",
                "Checked out" if ser["check_out"] else "In",
            ])
        return response


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
