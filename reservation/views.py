from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from . import serializers
from .models import ReservableResource, Reservation
from .utils.permission_classes import ReservationManagementPermission
from .services.reservation_service import (
    create_reservation, cancel_reservation, _overlapping_qs, ReservationError,
)
from .services.payment_service import pay_advance
from member.models import Member
from core.utils.pagination import CustomPageNumberPagination

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class ReservableResourceView(APIView):
    def get_permissions(self):
        if self.request.method in ("POST", "PATCH"):
            return [ReservationManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = ReservableResource.objects.filter(is_active=True)
        rtype = request.query_params.get("resource_type")
        if rtype:
            qs = qs.filter(resource_type=rtype)
        data = serializers.ReservableResourceSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Resources", data=data))

    def post(self, request):
        serializer = serializers.ReservableResourceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Resource created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class ReservableResourceDetailView(APIView):
    permission_classes = [ReservationManagementPermission]

    def patch(self, request, resource_id):
        try:
            resource = ReservableResource.objects.get(id=resource_id)
        except ReservableResource.DoesNotExist:
            return Response(_envelope(404, "failed", "Resource not found"),
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.ReservableResourceSerializer(
            resource, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(200, "success", "Resource updated",
                            data=serializer.data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = serializers.AvailabilityQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        vd = serializer.validated_data
        try:
            resource = ReservableResource.objects.get(id=vd["resource_id"])
        except ReservableResource.DoesNotExist:
            return Response(_envelope(404, "failed", "Resource not found"),
                            status=status.HTTP_404_NOT_FOUND)
        used = _overlapping_qs(resource, vd["start_time"], vd["end_time"]).count()
        available = max(resource.capacity - used, 0)
        return Response(_envelope(200, "success", "Availability", data={
            "resource_id": resource.id, "capacity": resource.capacity,
            "used": used, "available": available,
            "is_available": available > 0,
        }))


class ReservationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Reservation.objects.select_related(
            "member", "resource").filter(is_active=True)
        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        member_id = request.query_params.get("member_id")
        if member_id:
            qs = qs.filter(member_id=member_id)
        resource_id = request.query_params.get("resource_id")
        if resource_id:
            qs = qs.filter(resource_id=resource_id)
        # Bug 5.1: search by member name / ID, newest first (serial)
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(member__member_ID__icontains=search) |
                Q(member__first_name__icontains=search) |
                Q(member__last_name__icontains=search) |
                Q(resource__name__icontains=search))
        qs = qs.order_by("-created_at")
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.ReservationViewSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.CreateReservationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        vd = serializer.validated_data
        try:
            resource = ReservableResource.objects.get(id=vd["resource_id"])
            member = Member.objects.get(id=vd["member_id"])
            reservation = create_reservation(
                resource=resource, member=member,
                start_time=vd["start_time"], end_time=vd["end_time"],
                party_size=vd["party_size"], note=vd.get("note", ""),
                created_by=request.user)
            return Response(_envelope(201, "success", "Reservation created",
                            data=serializers.ReservationViewSerializer(reservation).data),
                            status=status.HTTP_201_CREATED)
        except ReservationError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except ReservableResource.DoesNotExist:
            return Response(_envelope(404, "failed", "Resource not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Member.DoesNotExist:
            return Response(_envelope(404, "failed", "Member not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PayReservationAdvanceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        serializer = serializers.PayAdvanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        try:
            reservation = Reservation.objects.get(id=reservation_id)
            invoice = pay_advance(
                reservation=reservation,
                payment_mode=serializer.validated_data["payment_mode"],
                processed_by=request.user)
            from member_financial_management.serializers import InvoiceSerializer
            return Response(_envelope(201, "success", "Advance paid, reservation confirmed",
                            data=InvoiceSerializer(invoice).data),
                            status=status.HTTP_201_CREATED)
        except Reservation.DoesNotExist:
            return Response(_envelope(404, "failed", "Reservation not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except ReservationError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelReservationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.get(id=reservation_id)
            cancel_reservation(reservation=reservation)
            return Response(_envelope(200, "success", "Reservation cancelled",
                            data=serializers.ReservationViewSerializer(reservation).data))
        except Reservation.DoesNotExist:
            return Response(_envelope(404, "failed", "Reservation not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except ReservationError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
