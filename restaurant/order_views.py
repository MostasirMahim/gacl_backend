from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from . import serializers
from .models import (
    Restaurant, RestaurantOrder, RestaurantItem, RestaurantItemSetting,
    SpicyLevel, RestaurantInventoryItem, RestaurantInventoryTransaction,
    RestaurantItemRecipe,
)
from .utils.permission_classes import RestaurantManagementPermission
from .services.order_service import (
    create_order, verify_otp, advance_kitchen_status, OrderError,
)
from .services.billing_service import bill_order
from member.models import Member
from attendance.models import Guest
from core.utils.pagination import CustomPageNumberPagination
from django.db import transaction
from decimal import Decimal

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class SpicyLevelView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = SpicyLevel.objects.filter(is_active=True)
        data = serializers.SpicyLevelSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Spicy levels", data=data))

    def post(self, request):
        serializer = serializers.SpicyLevelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Spicy level created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class RestaurantItemSettingView(APIView):
    """Restaurant admin sets spicy_selectable / public-show per item."""
    permission_classes = [RestaurantManagementPermission]

    def post(self, request):
        serializer = serializers.RestaurantItemSettingSerializer(data=request.data)
        if serializer.is_valid():
            item = serializer.validated_data["item"]
            obj, _ = RestaurantItemSetting.objects.update_or_create(
                item=item,
                defaults={
                    "spicy_selectable": serializer.validated_data.get("spicy_selectable", False),
                    "is_public_show": serializer.validated_data.get("is_public_show", False),
                })
            return Response(_envelope(200, "success", "Item setting saved",
                            data=serializers.RestaurantItemSettingSerializer(obj).data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class PublicMenuView(APIView):
    """Menu items the restaurant admin posted for show (logged-in members only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        restaurant_id = request.query_params.get("restaurant_id")
        qs = RestaurantItem.objects.filter(
            setting__is_public_show=True, is_active=True, availability=True)
        if restaurant_id:
            qs = qs.filter(restaurant_id=restaurant_id)
        from .serializers import RestaurantItemViewSerializer
        try:
            data = RestaurantItemViewSerializer(qs, many=True).data
        except Exception:
            data = list(qs.values("id", "name", "selling_price", "description"))
        return Response(_envelope(200, "success", "Public menu", data=data))


class RestaurantOrderView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request):
        qs = RestaurantOrder.objects.prefetch_related("items").filter(is_active=True)
        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        restaurant_id = request.query_params.get("restaurant_id")
        if restaurant_id:
            qs = qs.filter(restaurant_id=restaurant_id)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.RestaurantOrderViewSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        vd = serializer.validated_data
        try:
            restaurant = Restaurant.objects.get(id=vd["restaurant_id"])
            member = Member.objects.get(id=vd["member_id"])
            guest = None
            if vd.get("guest_id"):
                guest = Guest.objects.get(id=vd["guest_id"])
            order = create_order(
                restaurant=restaurant, member=member,
                items=vd["items"], serve_location=vd["serve_location"],
                room_number=vd.get("room_number", ""), guest=guest,
                waiter=request.user if vd["placed_by"] == "waiter" else None,
                placed_by=vd["placed_by"], note=vd.get("note", ""),
                require_otp=vd["require_otp"],
            )
            return Response(_envelope(201, "success",
                            "Order created" + (" (OTP sent)" if vd["require_otp"] else ""),
                            data=serializers.RestaurantOrderViewSerializer(order).data),
                            status=status.HTTP_201_CREATED)
        except OrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Restaurant.DoesNotExist:
            return Response(_envelope(404, "failed", "Restaurant not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Member.DoesNotExist:
            return Response(_envelope(404, "failed", "Member not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Guest.DoesNotExist:
            return Response(_envelope(404, "failed", "Guest not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyOrderOtpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        serializer = serializers.VerifyOtpSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        try:
            order = RestaurantOrder.objects.get(id=order_id)
            verify_otp(order=order, otp_code=serializer.validated_data["otp_code"])
            return Response(_envelope(200, "success", "Order confirmed",
                            data=serializers.RestaurantOrderViewSerializer(order).data))
        except RestaurantOrder.DoesNotExist:
            return Response(_envelope(404, "failed", "Order not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except OrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class KitchenOrderView(APIView):
    """Kitchen display: list confirmed/preparing/ready orders + advance status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        restaurant_id = request.query_params.get("restaurant_id")
        qs = RestaurantOrder.objects.prefetch_related("items").filter(
            status__in=["confirmed", "preparing", "ready"], is_active=True)
        if restaurant_id:
            qs = qs.filter(restaurant_id=restaurant_id)
        data = serializers.RestaurantOrderViewSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Kitchen queue", data=data))

    def patch(self, request, order_id):
        serializer = serializers.KitchenStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        try:
            order = RestaurantOrder.objects.get(id=order_id)
            advance_kitchen_status(
                order=order, target_status=serializer.validated_data["target_status"])
            return Response(_envelope(200, "success", "Order status updated",
                            data=serializers.RestaurantOrderViewSerializer(order).data))
        except RestaurantOrder.DoesNotExist:
            return Response(_envelope(404, "failed", "Order not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except OrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class BillOrderView(APIView):
    permission_classes = [RestaurantManagementPermission]

    def post(self, request, order_id):
        serializer = serializers.BillOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        vd = serializer.validated_data
        try:
            order = RestaurantOrder.objects.get(id=order_id)
            invoice = bill_order(
                order=order, payment_mode=vd["payment_mode"],
                processed_by=request.user,
                discount=Decimal(str(vd.get("discount", 0))),
                tax=Decimal(str(vd.get("tax", 0))))
            from member_financial_management.serializers import InvoiceSerializer
            return Response(_envelope(201, "success", "Order billed",
                            data=InvoiceSerializer(invoice).data),
                            status=status.HTTP_201_CREATED)
        except RestaurantOrder.DoesNotExist:
            return Response(_envelope(404, "failed", "Order not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except OrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantInventoryItemView(APIView):
    def get_permissions(self):
        if self.request.method in ("POST", "PATCH"):
            return [RestaurantManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = RestaurantInventoryItem.objects.filter(is_active=True)
        restaurant_id = request.query_params.get("restaurant_id")
        if restaurant_id:
            qs = qs.filter(restaurant_id=restaurant_id)
        if request.query_params.get("low_only") == "true":
            qs = [i for i in qs if i.is_low]
        data = serializers.RestaurantInventoryItemSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Inventory items", data=data))

    def post(self, request):
        serializer = serializers.RestaurantInventoryItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Inventory item created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class RestaurantInventoryMovementView(APIView):
    """Record stock in (purchase) / out (wastage). Updates current_quantity."""
    permission_classes = [RestaurantManagementPermission]

    @transaction.atomic
    def post(self, request):
        serializer = serializers.RestaurantInventoryTransactionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        movement = serializer.validated_data["movement"]
        inv = serializer.validated_data["inventory_item"]
        qty = serializer.validated_data["quantity"]
        if movement == "in":
            inv.current_quantity = inv.current_quantity + qty
        else:
            inv.current_quantity = inv.current_quantity - qty
        inv.save(update_fields=["current_quantity", "updated_at"])
        serializer.save(created_by=request.user)
        return Response(_envelope(201, "success", "Stock movement recorded",
                        data=serializer.data), status=status.HTTP_201_CREATED)


class RestaurantItemRecipeView(APIView):
    permission_classes = [RestaurantManagementPermission]

    def post(self, request):
        serializer = serializers.RestaurantItemRecipeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Recipe line saved",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
