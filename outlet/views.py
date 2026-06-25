from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from decimal import Decimal
import logging

from . import serializers
from .models import (
    Outlet, OutletItem, OutletItemCategory, CrossOrderingRule, OutletOrder,
    OutletInventoryItem,
)
from .utils.permission_classes import OutletManagementPermission
from .services.order_service import (
    create_outlet_order, verify_otp, advance_status, OutletOrderError,
)
from .services.billing_service import bill_outlet_order
from member.models import Member
from attendance.models import Guest
from restaurant.models import RestaurantItem
from core.utils.pagination import CustomPageNumberPagination

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class OutletView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = Outlet.objects.filter(is_active=True)
        otype = request.query_params.get("outlet_type")
        if otype:
            qs = qs.filter(outlet_type=otype)
        data = serializers.OutletSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Outlets", data=data))

    def post(self, request):
        serializer = serializers.OutletSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Outlet created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class OutletItemCategoryView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = OutletItemCategory.objects.filter(is_active=True)
        data = serializers.OutletItemCategorySerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Categories", data=data))

    def post(self, request):
        serializer = serializers.OutletItemCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Category created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class OutletItemView(APIView):
    """Outlet admin posts menu items here."""
    def get_permissions(self):
        if self.request.method in ("POST", "PATCH"):
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = OutletItem.objects.prefetch_related("media").filter(is_active=True)
        outlet_id = request.query_params.get("outlet_id")
        if outlet_id:
            qs = qs.filter(outlet_id=outlet_id)
        if request.query_params.get("public") == "true":
            qs = qs.filter(is_public_show=True, availability=True)
        data = serializers.OutletItemSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Outlet items", data=data))

    def post(self, request):
        serializer = serializers.OutletItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Item created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class CrossOrderingRuleView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = CrossOrderingRule.objects.filter(is_active=True)
        data = serializers.CrossOrderingRuleSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Cross-ordering rules", data=data))

    def post(self, request):
        serializer = serializers.CrossOrderingRuleSerializer(data=request.data)
        if serializer.is_valid():
            obj, _ = CrossOrderingRule.objects.update_or_create(
                source_type=serializer.validated_data["source_type"],
                target_type=serializer.validated_data["target_type"],
                defaults={
                    "allowed": serializer.validated_data.get("allowed", True),
                    "requires_room_number": serializer.validated_data.get(
                        "requires_room_number", False),
                })
            return Response(_envelope(200, "success", "Rule saved",
                            data=serializers.CrossOrderingRuleSerializer(obj).data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class OutletOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OutletOrder.objects.prefetch_related("items").filter(is_active=True)
        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        outlet_id = request.query_params.get("outlet_id")
        if outlet_id:
            qs = qs.filter(outlet_id=outlet_id)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = serializers.OutletOrderViewSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = serializers.CreateOutletOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        vd = serializer.validated_data
        try:
            outlet = Outlet.objects.get(id=vd["outlet_id"])
            member = Member.objects.get(id=vd["member_id"])
            guest = Guest.objects.get(id=vd["guest_id"]) if vd.get("guest_id") else None
            order = create_outlet_order(
                outlet=outlet, member=member, items=vd["items"], guest=guest,
                waiter=request.user if vd["placed_by"] == "waiter" else None,
                placed_by=vd["placed_by"], room_number=vd.get("room_number", ""),
                note=vd.get("note", ""), require_otp=vd["require_otp"],
            )
            return Response(_envelope(201, "success",
                            "Order created" + (" (OTP sent)" if vd["require_otp"] else ""),
                            data=serializers.OutletOrderViewSerializer(order).data),
                            status=status.HTTP_201_CREATED)
        except OutletOrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Outlet.DoesNotExist:
            return Response(_envelope(404, "failed", "Outlet not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Member.DoesNotExist:
            return Response(_envelope(404, "failed", "Member not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Guest.DoesNotExist:
            return Response(_envelope(404, "failed", "Guest not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except (OutletItem.DoesNotExist, RestaurantItem.DoesNotExist):
            return Response(_envelope(404, "failed", "Ordered item not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyOutletOtpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        serializer = serializers.VerifyOtpSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        try:
            order = OutletOrder.objects.get(id=order_id)
            verify_otp(order=order, otp_code=serializer.validated_data["otp_code"])
            return Response(_envelope(200, "success", "Order confirmed",
                            data=serializers.OutletOrderViewSerializer(order).data))
        except OutletOrder.DoesNotExist:
            return Response(_envelope(404, "failed", "Order not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except OutletOrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class OutletKitchenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OutletOrder.objects.prefetch_related("items").filter(
            status__in=["confirmed", "preparing", "ready"], is_active=True)
        outlet_id = request.query_params.get("outlet_id")
        if outlet_id:
            qs = qs.filter(outlet_id=outlet_id)
        data = serializers.OutletOrderViewSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Preparation queue", data=data))

    def patch(self, request, order_id):
        serializer = serializers.StatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        try:
            order = OutletOrder.objects.get(id=order_id)
            advance_status(order=order,
                           target_status=serializer.validated_data["target_status"])
            return Response(_envelope(200, "success", "Order status updated",
                            data=serializers.OutletOrderViewSerializer(order).data))
        except OutletOrder.DoesNotExist:
            return Response(_envelope(404, "failed", "Order not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except OutletOrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class BillOutletOrderView(APIView):
    permission_classes = [OutletManagementPermission]

    def post(self, request, order_id):
        serializer = serializers.BillOutletOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(_envelope(400, "failed", "Bad request",
                            errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        vd = serializer.validated_data
        try:
            order = OutletOrder.objects.get(id=order_id)
            invoice = bill_outlet_order(
                order=order, payment_mode=vd["payment_mode"],
                processed_by=request.user,
                discount=Decimal(str(vd.get("discount", 0))),
                tax=Decimal(str(vd.get("tax", 0))))
            from member_financial_management.serializers import InvoiceSerializer
            return Response(_envelope(201, "success", "Order billed",
                            data=InvoiceSerializer(invoice).data),
                            status=status.HTTP_201_CREATED)
        except OutletOrder.DoesNotExist:
            return Response(_envelope(404, "failed", "Order not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except OutletOrderError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OutletInventoryItemView(APIView):
    def get_permissions(self):
        if self.request.method in ("POST", "PATCH"):
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = OutletInventoryItem.objects.filter(is_active=True)
        outlet_id = request.query_params.get("outlet_id")
        if outlet_id:
            qs = qs.filter(outlet_id=outlet_id)
        if request.query_params.get("low_only") == "true":
            qs = [i for i in qs if i.is_low]
        data = serializers.OutletInventoryItemSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Inventory items", data=data))

    def post(self, request):
        serializer = serializers.OutletInventoryItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Inventory item created",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


class OutletInventoryMovementView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        from .models import OutletInventoryTransaction
        qs = OutletInventoryTransaction.objects.select_related(
            "inventory_item").all().order_by("-created_at")
        inv_id = request.query_params.get("inventory_item")
        if inv_id:
            qs = qs.filter(inventory_item_id=inv_id)
        outlet_id = request.query_params.get("outlet_id")
        if outlet_id:
            qs = qs.filter(inventory_item__outlet_id=outlet_id)
        qs = qs[:200]
        data = serializers.OutletInventoryTransactionSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Stock movements", data=data))

    @transaction.atomic
    def post(self, request):
        serializer = serializers.OutletInventoryTransactionSerializer(data=request.data)
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


class OutletItemRecipeView(APIView):
    permission_classes = [OutletManagementPermission]

    def post(self, request):
        serializer = serializers.OutletItemRecipeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(201, "success", "Recipe line saved",
                            data=serializer.data), status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors), status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------
# Detail views added for QA: outlet update, category update/delete,
# item update/delete. These give the frontend full management ability.
# ---------------------------------------------------------------
class OutletDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return Outlet.objects.get(id=pk)
        except Outlet.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Outlet not found"),
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_envelope(200, "success", "Outlet detail",
                        data=serializers.OutletSerializer(obj).data))

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Outlet not found"),
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.OutletSerializer(obj, data=request.data,
                                                  partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(200, "success", "Outlet updated",
                            data=serializer.data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Outlet not found"),
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return Response(_envelope(200, "success", "Outlet deactivated"))


class OutletItemCategoryDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return OutletItemCategory.objects.get(id=pk)
        except OutletItemCategory.DoesNotExist:
            return None

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Category not found"),
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.OutletItemCategorySerializer(
            obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(200, "success", "Category updated",
                            data=serializer.data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Category not found"),
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return Response(_envelope(200, "success", "Category deleted"))


class OutletItemDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [OutletManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return OutletItem.objects.get(id=pk)
        except OutletItem.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Item not found"),
                            status=status.HTTP_404_NOT_FOUND)
        return Response(_envelope(200, "success", "Item detail",
                        data=serializers.OutletItemSerializer(obj).data))

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Item not found"),
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.OutletItemSerializer(
            obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(_envelope(200, "success", "Item updated",
                            data=serializer.data))
        return Response(_envelope(400, "failed", "Bad request",
                        errors=serializer.errors),
                        status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(_envelope(404, "failed", "Item not found"),
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return Response(_envelope(200, "success", "Item deleted"))
