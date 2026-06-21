from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from . import serializers
from .models import Vendor, VendorServiceCategory, VendorServiceOffer
from .utils.permission_classes import VendorManagementPermission
from .services.vendor_service import select_offer, record_vendor_payment, VendorError

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class VendorView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [VendorManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = Vendor.objects.filter(is_active=True)
        return Response(_envelope(200, "success", "Vendors",
                        data=serializers.VendorSerializer(qs, many=True).data))

    def post(self, request):
        s = serializers.VendorSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(_envelope(201, "success", "Vendor created", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class VendorServiceCategoryView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [VendorManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = VendorServiceCategory.objects.filter(is_active=True)
        return Response(_envelope(200, "success", "Categories",
                        data=serializers.VendorServiceCategorySerializer(qs, many=True).data))

    def post(self, request):
        s = serializers.VendorServiceCategorySerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(_envelope(201, "success", "Category created", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class VendorServiceOfferView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [VendorManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = VendorServiceOffer.objects.filter(is_active=True)
        category_id = request.query_params.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)
        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        return Response(_envelope(200, "success", "Offers",
                        data=serializers.VendorServiceOfferSerializer(qs, many=True).data))

    def post(self, request):
        s = serializers.VendorServiceOfferSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(_envelope(201, "success", "Offer created", data=s.data),
                            status=status.HTTP_201_CREATED)
        return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                        status=status.HTTP_400_BAD_REQUEST)


class VendorOfferSelectView(APIView):
    """Select an offer -> it becomes the active vendor; others in the category disabled."""
    permission_classes = [VendorManagementPermission]

    def post(self, request, offer_id):
        try:
            offer = VendorServiceOffer.objects.get(id=offer_id)
            select_offer(offer=offer)
            return Response(_envelope(200, "success", "Offer selected; others disabled",
                            data=serializers.VendorServiceOfferSerializer(offer).data))
        except VendorServiceOffer.DoesNotExist:
            return Response(_envelope(404, "failed", "Offer not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except VendorError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)


class VendorPaymentView(APIView):
    permission_classes = [VendorManagementPermission]

    def post(self, request, offer_id):
        s = serializers.VendorPaymentInputSerializer(data=request.data)
        if not s.is_valid():
            return Response(_envelope(400, "failed", "Bad request", errors=s.errors),
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            offer = VendorServiceOffer.objects.get(id=offer_id)
            payment = record_vendor_payment(
                offer=offer, amount=s.validated_data["amount"],
                note=s.validated_data.get("note", ""), created_by=request.user)
            return Response(_envelope(201, "success", "Vendor payment recorded",
                            data=serializers.VendorPaymentSerializer(payment).data),
                            status=status.HTTP_201_CREATED)
        except VendorServiceOffer.DoesNotExist:
            return Response(_envelope(404, "failed", "Offer not found"),
                            status=status.HTTP_404_NOT_FOUND)
        except VendorError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
