from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from . import serializers
from .models import RestaurantCuisineCategory, RestaurantCategory, Restaurant, RestaurantItemCategory, RestaurantItem
import logging
from activity_log.tasks import log_activity_task
from activity_log.utils.functions import request_data_activity_log
from member_financial_management.models import Invoice, InvoiceItem, InvoiceType, Income, IncomeReceivingType, Due, MemberDue
from member_financial_management.utils.functions import generate_unique_invoice_number
from member.models import Member
from django.db import transaction
from functools import reduce
from datetime import date, datetime

from member_financial_management.serializers import InvoiceSerializer
from core.utils.pagination import CustomPageNumberPagination
from promo_code_app.models import AppliedPromoCode
from django.core.cache import cache
from django.utils.http import urlencode
import pandas as pd
import pdb
from member_financial_management.models import Transaction, PaymentMethod, Payment, SaleType, Sale
from member_financial_management.utils.functions import generate_unique_invoice_number
from .utils.permission_classes import RestaurantManagementPermission
from member_financial_management.utils.permission_classes import MemberFinancialManagementPermission
logger = logging.getLogger("myapp")


class RestaurantCuisineCategoryView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            serializer = serializers.RestaurantCuisineCategorySerializer(
                data=request.data)
            if serializer.is_valid():
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created a new Restaurant cuisine category",
                )
                cache.delete_pattern("restaurant_cuisines::*")
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Cuisine category was successfully created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User tried to create a new Restaurant cuisine category but faced an error",
                )
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to create a new Restaurant cuisine category but faced an error",
            )
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
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"restaurant_cuisines::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            # Only hit DB if cache miss
            cuisines = RestaurantCuisineCategory.objects.filter(
                is_active=True).order_by("id")

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                cuisines, request=request, view=self)
            serializer = serializers.RestaurantCuisineCategorySerializer(
                paginated_queryset, many=True)

            response_data = {
                "code": 200,
                "status": "success",
                "message": "viewing all available cuisines",
                "data": serializer.data
            }

            # Use paginator to build full response (with count, next, previous)
            final_response = paginator.get_paginated_response(response_data)

            # Cache the actual response content (final_response.data)
            cache.set(cache_key, final_response.data, timeout=60 * 30)

            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all restaurant cuisines",
            )

            return final_response

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all restaurant cuisines but faced an error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantCategoryView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            serializer = serializers.RestaurantCategorySerializer(
                data=request.data)
            if serializer.is_valid():
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created a new restaurant category",
                )
                cache.delete_pattern("restaurant_categories::*")
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Category was successfully created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User made a bad request in Restaurant category creation API",
                )
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to crate Restaurant category and failed",
            )
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
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"restaurant_categories::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            paginator = CustomPageNumberPagination()
            categories = RestaurantCategory.objects.filter(is_active=True)
            paginated_queryset = paginator.paginate_queryset(
                categories, request=request, view=self)
            serializer = serializers.RestaurantCategorySerializer(
                paginated_queryset, many=True)
            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "viewing all available categories",
                "data": serializer.data
            }, status=200)
            cache.set(cache_key, final_response.data, timeout=60 * 30)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all restaurant categories",
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all restaurant categories but failed",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        else:
            return [IsAuthenticated()]

    def get(self, request):
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"restaurants::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            # Only hit DB if cache miss
            paginator = CustomPageNumberPagination()
            data = Restaurant.objects.select_related(
                "cuisine_type", "restaurant_type").filter(is_active=True)
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.RestaurantViewSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all restaurants",
            )
            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "Viewing all available restaurant",
                "data": serializer.data
            }, status=200)
            cache.set(cache_key, final_response.data, timeout=60 * 30)
            return final_response

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all restaurants but failed",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            })

    def post(self, request):
        try:
            serializer = serializers.RestaurantSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created a new restaurant",
                )
                cache.delete_pattern("restaurants::*")
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Restaurant was successfully created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User made a bad request while creating restaurant",
                )
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to create Restaurant and an error occurred",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemCategoryView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            serializer = serializers.RestaurantItemCategorySerializer(
                data=request.data)
            if serializer.is_valid():
                instance = serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created a new restaurant item category",
                )
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Item category was successfully created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)

            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User tried to create a new restaurant item category and made a bad request",
                )
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to create a new restaurant item category and an error occurred",
            )
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
            paginator = CustomPageNumberPagination()
            cuisines = RestaurantItemCategory.objects.filter(is_active=True)
            paginated_queryset = paginator.paginate_queryset(
                cuisines, request=request, view=self)
            serializer = serializers.RestaurantItemCategorySerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all restaurant items categories",
            )
            return paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "viewing all available item categories",
                "data": serializer.data
            })
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all available item categories but failed",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        else:
            return [IsAuthenticated()]

    def get(self, request):
        try:
            restaurant_id = request.query_params.get("restaurant")
            if restaurant_id:
                if not Restaurant.objects.filter(id=restaurant_id).exists():
                    return Response({
                        "code": 400,
                        "status": "bad request",
                        "message": "Something want wrong",
                        "errors": {
                            "restaurant_id": ["Not restaurant exist with this id"]
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    query_items = sorted(request.query_params.items())
                    query_string = urlencode(
                        query_items) if query_items else "default"
                    cache_key = f"restaurant_items::{query_string}"
                    cached_response = cache.get(cache_key)
                    if cached_response:
                        return Response(cached_response, status=200)
                    # Only hit DB if cache miss
                    paginator = CustomPageNumberPagination()
                    items = RestaurantItem.objects.prefetch_related("item_media").select_related("category", "restaurant").filter(
                        restaurant__id=restaurant_id).order_by("id")
                    paginated_queryset = paginator.paginate_queryset(
                        items, request=request, view=self)
                    serializer = serializers.RestaurantItemForViewSerializer(
                        paginated_queryset, many=True)
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="View",
                        severity_level="info",
                        description="User viewed all restaurant items",
                    )
                    final_response = paginator.get_paginated_response({
                        "code": 200,
                        "status": "success",
                        "message": "Viewing all restaurant items",
                        "data": serializer.data
                    })
                    cache.set(cache_key, final_response.data, timeout=60 * 30)
                    return final_response
            else:
                return Response({
                    "code": 400,
                    "status": "bad request",
                    "message": "Something want wrong",
                    "errors": {
                        "query_param": ["Missing required query parameter restaurant"]
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all restaurant items but failed",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.RestaurantItemSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created a new restaurant item",
                )
                try:
                    cache.delete_pattern("restaurant_items::*")
                    cache.delete_pattern("restaurant_public_menu::*")
                except Exception:
                    pass
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Successfully created restaurant item",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User made a bad request",
                )
                return Response({
                    "code": 400,
                    "status": "success",
                    "message": "Something went wrong",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to create a new restaurant item but failed",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemMediaView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [RestaurantManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        try:
            serializer = serializers.RestaurantItemMediaSerializer(
                data=request.data)
            if serializer.is_valid():
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User added restaurant item media",
                )
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Restaurant item media was successfully added"
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({"code": 400,
                                 "status": "failed",
                                 "message": "Bad request",
                                 "errors": serializer.errors
                                 }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to add restaurant item media but failed",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class RestaurantItemBuyView(APIView):
#     permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

#     def post(self, request):
#         try:
#             serializer = serializers.RestaurantItemBuySerializer(
#                 data=request.data)
#             if serializer.is_valid():
#                 restaurant = serializer.validated_data["restaurant"]
#                 restaurant_items = serializer.validated_data["restaurant_items"]
#                 member = serializer.validated_data["member_ID"]
#                 member = Member.objects.get(member_ID=member)
#                 total_amount = reduce(
#                     lambda acc, item: acc + item["id"].selling_price*item["quantity"], restaurant_items, 0)
#                 invoice_type, _ = InvoiceType.objects.get_or_create(
#                     name="Restaurant")
#                 promo_code = serializer.validated_data["promo_code"]
#                 discount = 0
#                 if promo_code != None:
#                     if promo_code.percentage is not None:
#                         percentage = promo_code.percentage
#                         discount = (percentage/100) * total_amount
#                         total_amount = total_amount - discount
#                     else:
#                         discount = promo_code.amount
#                         if discount <= total_amount:
#                             total_amount = total_amount - discount
#                         else:
#                             discount = total_amount
#                             total_amount = 0
#                     promo_code.remaining_limit -= 1
#                     promo_code.save(update_fields=["remaining_limit"])
#                 else:
#                     promo_code = ""
#                 with transaction.atomic():
#                     invoice = Invoice.objects.create(
#                         currency="BDT",
#                         invoice_number=generate_unique_invoice_number(),
#                         balance_due=total_amount,
#                         paid_amount=0,
#                         issue_date=date.today(),
#                         total_amount=total_amount,
#                         is_full_paid=False,
#                         status="unpaid",
#                         invoice_type=invoice_type,
#                         generated_by=request.user,
#                         member=member,
#                         restaurant=restaurant,
#                         discount=discount,
#                         promo_code=promo_code
#                     )
#                     if promo_code != "":
#                         AppliedPromoCode.objects.create(
#                             discounted_amount=discount, promo_code=promo_code, used_by=member)
#                     restaurant_items_objs = []
#                     for item in restaurant_items:
#                         restaurant_items_objs.append(item["id"].id)
#                     invoice_item = InvoiceItem.objects.create(
#                         invoice=invoice
#                     )
#                     invoice_item.restaurant_items.set(restaurant_items_objs)
#                 return Response({
#                     "code": 201,
#                     "status": "success",
#                     "message": "Invoice created successfully",
#                     "data": InvoiceSerializer(invoice).data
#                 }, status=status.HTTP_201_CREATED)
#             else:
#                 return Response({
#                     "code": 400,
#                     "status": "failed",
#                     "message": "bad request",
#                     "errors": serializer.errors
#                 }, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.exception(str(e))
#             return Response({
#                 "code": 500,
#                 "status": "failed",
#                 "message": "Something went wrong. Please try again.",
#                 "errors": {
#                     "server_error": [str(e)]
#                 }
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RestaurantItemBuyView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            serializer = serializers.RestaurantItemBuySerializer(data=request.data)
            if serializer.is_valid():
                restaurant = serializer.validated_data["restaurant"]
                restaurant_items = serializer.validated_data["restaurant_items"]
                member_id = serializer.validated_data["member_ID"]
                member = Member.objects.get(member_ID=member_id)

                # Calculate total amount
                total_amount = reduce(
                    lambda acc, item: acc + item["id"].selling_price * item["quantity"],
                    restaurant_items,
                    0
                )

                # Get or create invoice type
                invoice_type, _ = InvoiceType.objects.get_or_create(name="Restaurant")

                promo_code_obj = serializer.validated_data.get("promo_code")
                discount = 0
                promo_code_str = ""  

                if promo_code_obj is not None:
                    if promo_code_obj.percentage is not None:
                        discount = (promo_code_obj.percentage / 100) * total_amount
                    else:
                        discount = promo_code_obj.amount

                    # Apply discount limits
                    if discount > total_amount:
                        discount = total_amount
                    total_amount -= discount

                    # Update promo code remaining limit
                    promo_code_obj.remaining_limit -= 1
                    promo_code_obj.save(update_fields=["remaining_limit"])

                    promo_code_str = str(promo_code_obj)  

                # Validate restaurant_items IDs
                restaurant_items_ids = [item["id"].id for item in restaurant_items]
                valid_ids = set(
                    RestaurantItem.objects.filter(id__in=restaurant_items_ids).values_list('id', flat=True)
                )
                if set(restaurant_items_ids) != valid_ids:
                    logger.error("Invalid restaurant item IDs sent in request")
                    return Response({
                        "code": 400,
                        "status": "failed",
                        "message": "Invalid restaurant item IDs",
                        "data": {
                            "invalid_ids": list(set(restaurant_items_ids) - valid_ids)
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)

                with transaction.atomic():
                    invoice = Invoice.objects.create(
                        currency="BDT",
                        invoice_number=generate_unique_invoice_number(),
                        balance_due=total_amount,
                        paid_amount=0,
                        issue_date=date.today(),
                        total_amount=total_amount,
                        is_full_paid=False,
                        status="unpaid",
                        invoice_type=invoice_type,
                        generated_by=request.user,
                        member=member,
                        restaurant=restaurant,
                        discount=discount,
                        promo_code=promo_code_str  
                    )

                    if promo_code_obj is not None:
                        AppliedPromoCode.objects.create(
                            discounted_amount=discount,
                            promo_code=promo_code_obj,
                            used_by=member
                        )

                    invoice_item = InvoiceItem.objects.create(invoice=invoice)
                    invoice_item.restaurant_items.set(valid_ids)
                    

                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "Invoice created successfully",
                    "data": InvoiceSerializer(invoice).data
                }, status=status.HTTP_201_CREATED)

            else:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Member.DoesNotExist:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Member not found"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong. Please try again.",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RestaurantUploadExcelView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            serializer = serializers.RestaurantExcelUpload(data=request.data)
            if serializer.is_valid():
                excel_file = serializer.validated_data["excel_file"]
                restaurant = serializer.validated_data["restaurant"]
                income_particular = serializer.validated_data["income_particular"]
                received_from = serializer.validated_data["received_from"]
                uploaded_file = excel_file
                try:
                    # Do not modify anything below this line ->>>>>>
                    file_data_cl = None
                    if uploaded_file.name.endswith('.xlsx'):
                        file_data_cl = pd.read_excel(
                            uploaded_file, engine='openpyxl', dtype=str)
                    elif uploaded_file.name.endswith('.xls'):
                        file_data_cl = pd.read_excel(
                            uploaded_file, engine='xlrd', dtype=str)

                    if file_data_cl is not None:  # Ensure file was read successfully
                        # pandas clean starts here, do not write anything below this line
                        file_data_cl = file_data_cl.dropna(how='all')

                        # Extract and format the date range
                        cell_data = file_data_cl.iat[2, 5]
                        date_range_payment = cell_data.strip()
                        p_start_date, p_end_date = date_range_payment.split(
                            " to ")
                        p_start_date = datetime.strptime(
                            p_start_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                        p_end_date = datetime.strptime(
                            p_end_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                        # print("checking dates: ", p_start_date, p_end_date)
                        if (p_start_date != p_end_date):
                            return Response({
                                "code": 400,
                                "status": "failed",
                                "message": "Invalid date range",
                                "errors": {
                                    "date_range": ["Invalid date range"]
                                }
                            }, status=400)

                        # Select relevant columns and rename them
                        file_data_cl = file_data_cl[['Unnamed: 0', 'Unnamed: 1', 'Unnamed: 2', 'Unnamed: 4',
                                                    'Unnamed: 5', 'Unnamed: 6', 'Unnamed: 8', 'Unnamed: 9', 'Unnamed: 10']]
                        file_data_cl.dropna(
                            subset=[file_data_cl.columns[1]], inplace=True)
                        file_data_cl = file_data_cl[~(
                            file_data_cl['Unnamed: 0'] == 'SL')]

                        file_data_cl.columns = [
                            'serial_number', 'sales_code', 'member_account', 'cash_amount', 'card_amount',
                            'due_amount', 'total', 'srv_charge', 'grand_total'
                        ]

                        # Add start and end dates
                        file_data_cl['Start_Date'] = p_start_date
                        file_data_cl['End_Date'] = p_end_date

                        # Convert numeric columns to appropriate types for summation
                        numeric_columns = ['cash_amount', 'card_amount',
                                           'due_amount', 'total', 'srv_charge', 'grand_total']
                        file_data_cl[numeric_columns] = file_data_cl[numeric_columns].apply(
                            pd.to_numeric, errors='coerce').fillna(0)
                        # do your operations here ->>>>
                        # Calculate totals for numeric columns
                        totals = {col: file_data_cl[col].sum()
                                  for col in numeric_columns}
                        totals['cash_amount'] = int(totals['cash_amount'])
                        totals['card_amount'] = int(totals['card_amount'])
                        totals['due_amount'] = int(totals['due_amount'])
                        totals['total'] = int(totals['total'])
                        totals['srv_charge'] = int(totals['srv_charge'])
                        totals['grand_total'] = int(totals['grand_total'])
                        # pandas clean ends here, do not write above this line
                except Exception as e:
                    return Response({
                        "code": 400,
                        "status": "failed",
                        "message": "Something went wrong",
                        "errors": {
                            "excel_file": ["There was an error while reading the file. Please check correct file has been uploaded."]
                        }
                    }, status=400)

                data = file_data_cl.to_dict(
                    orient='records')
                with transaction.atomic():
                    invoice_type, _ = InvoiceType.objects.get_or_create(
                        name="restaurant")
                    cash_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="cash")
                    card_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="card")
                    both_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="both")
                    sale_type, _ = SaleType.objects.get_or_create(
                        name="restaurant")
                    full_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                        name="full")
                    partial_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                        name="partial")
                    uploaded_member_data = []
                    for record in data:
                        paid_amount = record["cash_amount"] + \
                            record["card_amount"]
                        total_amount = record["grand_total"]
                        due_amount = record["due_amount"]
                        payment_method = None
                        start_date = datetime.strptime(
                            record["Start_Date"], "%Y-%m-%d").date()
                        if record["card_amount"] == 0 and record["cash_amount"] == 0:
                            payment_method = both_payment_method
                        elif record["card_amount"] != 0:
                            payment_method = card_payment_method
                        else:
                            payment_method = cash_payment_method
                        if paid_amount == total_amount:
                            income_receiving_type = full_income_receiving_type
                        else:
                            income_receiving_type = partial_income_receiving_type
                        try:
                            member = Member.objects.get(
                                member_ID=record["member_account"])
                            is_sale_number_exist = Sale.objects.filter(
                                sale_number=record["sales_code"]).exists()

                            if is_sale_number_exist:
                                uploaded_member_data.append({
                                    "member": record["member_account"],
                                    "sales_code": record["sales_code"],
                                    "status": "failed",
                                    "reason": "Sales code already exist",
                                })
                                continue
                        except Member.DoesNotExist:
                            uploaded_member_data.append({
                                "member": record["member_account"],
                                "sales_code": record["sales_code"],
                                "status": "failed",
                                "reason": "Member doesn't exist",
                            })
                            continue
                        invoice = Invoice.objects.create(
                            invoice_number=generate_unique_invoice_number(),
                            balance_due=record["due_amount"],
                            paid_amount=paid_amount,
                            due_date=start_date,
                            issue_date=datetime.today(),
                            total_amount=total_amount,
                            is_full_paid=paid_amount == total_amount,
                            status="paid" if total_amount == paid_amount else "partial_paid",
                            invoice_type=invoice_type,
                            generated_by=request.user,
                            member=member,
                            restaurant=restaurant)
                        transaction_obj = Transaction.objects.create(
                            amount=paid_amount,
                            member=member,
                            invoice=invoice,
                            payment_method=payment_method,
                            notes="This transaction was recorded from excel file."
                        )
                        payment_obj = Payment.objects.create(
                            payment_amount=paid_amount,
                            payment_status=invoice.status,
                            notes="This payment was recorded from excel file.",
                            transaction=transaction_obj,
                            invoice=invoice,
                            member=member,
                            payment_method=payment_method,
                            processed_by=request.user
                        )
                        due_date = start_date if record["due_amount"] == 0 else None
                        sale_obj = Sale.objects.create(sale_number=record["sales_code"],
                                                       sub_total=invoice.total_amount,
                                                       total_amount=invoice.total_amount,
                                                       payment_status=invoice.status,
                                                       due_date=due_date,
                                                       notes="Sale created from excel file.",
                                                       sale_source_type=sale_type,
                                                       customer=member,
                                                       payment_method=payment_method,
                                                       invoice=invoice
                                                       )
                        Income.objects.create(
                            receivable_amount=invoice.total_amount,
                            final_receivable=invoice.total_amount,
                            actual_received=invoice.paid_amount,
                            reaming_due=invoice.balance_due,
                            particular=income_particular,
                            received_from_type=received_from,
                            member=member,
                            received_by=payment_method,
                            sale=sale_obj,
                            receiving_type=income_receiving_type)
                        if due_amount > 0:  # it has due
                            due_obj = Due.objects.create(
                                original_amount=invoice.total_amount,
                                due_amount=invoice.balance_due,
                                paid_amount=invoice.paid_amount,
                                due_date=start_date,
                                payment_status=invoice.status,
                                member=member,
                                invoice=invoice,
                                payment=payment_obj,
                                transaction=transaction_obj,
                            )
                            MemberDue.objects.create(
                                amount_due=due_obj.due_amount,
                                due_date=start_date,
                                amount_paid=invoice.paid_amount,
                                payment_date=datetime.today(),
                                notes="This due has been recorded from excel file",
                                member=member,
                                due_reference=due_obj
                            )
                        uploaded_member_data.append({
                            "member_ID": member.member_ID,
                            "sales_code": record["sales_code"],
                            "status": "success",
                            "reason": "Successfully uploaded"
                        })
                    return Response({
                        "code": 201,
                        "status": "success",
                        "message": "Data uploaded successfully",
                        "data": uploaded_member_data
                    }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "bad request",
                    "errors": serializer.errors
                }, status=400)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong. Please try again.",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------
# Detail views added for QA: single restaurant detail + update (4.1),
# single item detail + update/delete (4.2).
# ---------------------------------------------------------------
class RestaurantDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [RestaurantManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return Restaurant.objects.select_related(
                "cuisine_type", "restaurant_type").get(id=pk, is_active=True)
        except Restaurant.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({"code": 404, "status": "failed",
                             "message": "Restaurant not found"},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({"code": 200, "status": "success",
                         "message": "Restaurant detail",
                         "data": serializers.RestaurantViewSerializer(obj).data})

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({"code": 404, "status": "failed",
                             "message": "Restaurant not found"},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.RestaurantUpdateSerializer(
            obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            try:
                cache.delete_pattern("restaurants::*")
                cache.delete_pattern("restaurant_public_menu::*")
            except Exception:
                pass
            return Response({"code": 200, "status": "success",
                             "message": "Restaurant updated",
                             "data": serializers.RestaurantViewSerializer(obj).data})
        return Response({"code": 400, "status": "failed",
                         "message": "Bad request", "errors": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({"code": 404, "status": "failed",
                             "message": "Restaurant not found"},
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        try:
            cache.delete_pattern("restaurants::*")
            cache.delete_pattern("restaurant_public_menu::*")
        except Exception:
            pass
        return Response({"code": 200, "status": "success",
                          "message": "Restaurant deactivated"})


class RestaurantItemDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [RestaurantManagementPermission()]
        return [IsAuthenticated()]

    def _get(self, pk):
        try:
            return RestaurantItem.objects.select_related(
                "restaurant", "category").get(id=pk, is_active=True)
        except RestaurantItem.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({"code": 404, "status": "failed",
                             "message": "Item not found"},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({"code": 200, "status": "success",
                         "message": "Item detail",
                         "data": serializers.RestaurantItemForViewSerializer(obj).data})

    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({"code": 404, "status": "failed",
                             "message": "Item not found"},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.RestaurantItemUpdateSerializer(
            obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            try:
                cache.delete_pattern("restaurant_items::*")
                cache.delete_pattern("restaurant_public_menu::*")
            except Exception:
                pass
            return Response({"code": 200, "status": "success",
                             "message": "Item updated",
                             "data": serializers.RestaurantItemForViewSerializer(obj).data})
        return Response({"code": 400, "status": "failed",
                         "message": "Bad request", "errors": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response({"code": 404, "status": "failed",
                             "message": "Item not found"},
                            status=status.HTTP_404_NOT_FOUND)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        try:
            cache.delete_pattern("restaurant_items::*")
            cache.delete_pattern("restaurant_public_menu::*")
        except Exception:
            pass
        return Response({"code": 200, "status": "success",
                          "message": "Item deleted"})


class RestaurantPublicMenuBySlugView(APIView):
    permission_classes = []  # Public endpoint

    def get(self, request, slug):
        try:
            cache_key = f"restaurant_public_menu::{slug}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)

            restaurant = Restaurant.objects.prefetch_related(
                "menu_sections", "testimonials"
            ).select_related("cuisine_type", "restaurant_type").get(slug=slug, is_active=True)

            # Serialize restaurant details
            restaurant_data = serializers.RestaurantViewSerializer(restaurant).data

            # Fetch testimonials using dynamic import
            from portal_management.serializers import RestaurantTestimonialSerializer
            testimonials = restaurant.testimonials.filter(is_active=True).order_by("-id")
            testimonials_data = RestaurantTestimonialSerializer(testimonials, many=True).data

            # Fetch and group sections and items
            sections = restaurant.menu_sections.filter(is_active=True).order_by("order")
            sections_data = []
            for sec in sections:
                items = RestaurantItem.objects.filter(
                    restaurant=restaurant, menu_section=sec, is_active=True
                ).prefetch_related("item_media").order_by("id")
                
                items_data = serializers.RestaurantItemForViewSerializer(items, many=True).data
                
                sections_data.append({
                    "id": sec.id,
                    "title": sec.title,
                    "cover_image": sec.cover_image.url if sec.cover_image else None,
                    "description": sec.description,
                    "order": sec.order,
                    "layout_type": sec.layout_type,
                    "items": items_data
                })

            final_data = {
                "restaurant": restaurant_data,
                "sections": sections_data,
                "testimonials": testimonials_data
            }

            final_response = {
                "code": 200,
                "status": "success",
                "message": "Public menu data fetched successfully",
                "data": final_data
            }

            cache.set(cache_key, final_response, timeout=60 * 10)  # cache for 10 minutes
            return Response(final_response, status=status.HTTP_200_OK)

        except Restaurant.DoesNotExist:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Restaurant not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GuestMemberLookupView(APIView):
    """
    Public endpoint: look up a member by their member_ID string.
    Returns only safe, non-sensitive display fields + the DB pk (needed
    to submit a guest order).  No authentication required — OTP on the
    member's registered email is the actual security gate.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        member_id_str = request.query_params.get("member_id", "").strip()
        if not member_id_str:
            return Response({
                "code": 400,
                "status": "failed",
                "message": "member_id query parameter is required",
                "errors": {"member_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            member = Member.objects.prefetch_related("emails").get(
                member_ID=member_id_str, is_active=True)
        except Member.DoesNotExist:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "No active member found with this Member ID"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Only expose safe fields — no phone, no address, no financials
        primary_email = member.emails.filter(is_active=True, is_primary=True).first()
        email_display = ""
        if primary_email:
            # Mask the email for display: jo***@example.com
            raw = primary_email.email
            at = raw.find("@")
            if at > 2:
                email_display = raw[:2] + "***" + raw[at:]
            else:
                email_display = "***" + raw[at:]

        return Response({
            "code": 200,
            "status": "success",
            "message": "Member found",
            "data": {
                "id": member.id,                     # DB pk — used in order payload
                "member_ID": member.member_ID,
                "full_name": f"{member.first_name} {member.last_name}".strip(),
                "email_hint": email_display,         # masked for display only
            }
        }, status=status.HTTP_200_OK)


class RestaurantPublicItemDetailBySlugView(APIView):
    permission_classes = []  # Public endpoint

    def get(self, request, restaurant_slug, item_slug):
        try:
            item = RestaurantItem.objects.select_related(
                "restaurant", "category", "menu_section"
            ).prefetch_related("item_media").get(
                restaurant__slug=restaurant_slug, slug=item_slug, is_active=True
            )

            # Fetch active reviews using dynamic import
            from portal_management.serializers import RestaurantItemReviewSerializer
            reviews = item.reviews.filter(is_active=True).order_by("-id")
            reviews_data = RestaurantItemReviewSerializer(reviews, many=True).data

            item_data = serializers.RestaurantItemForViewSerializer(item).data
            
            # Fetch related items (other items in same restaurant)
            related_items = RestaurantItem.objects.filter(
                restaurant=item.restaurant, is_active=True
            ).exclude(id=item.id)[:4]
            related_data = serializers.RestaurantItemForViewSerializer(related_items, many=True).data

            restaurant_data = serializers.RestaurantViewSerializer(item.restaurant).data

            final_data = {
                "item": item_data,
                "restaurant": restaurant_data,
                "reviews": reviews_data,
                "related_items": related_data
            }

            return Response({
                "code": 200,
                "status": "success",
                "message": "Item details fetched successfully",
                "data": final_data
            }, status=status.HTTP_200_OK)

        except RestaurantItem.DoesNotExist:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Item not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.permissions import AllowAny

class RestaurantPublicListView(APIView):
    """
    Public API to list all active, open restaurants for the default landing grid page.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"public_restaurants_list::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)

            paginator = CustomPageNumberPagination()
            restaurants = Restaurant.objects.select_related(
                "cuisine_type", "restaurant_type"
            ).filter(is_active=True, status="open").order_by("-id")
            
            paginated_queryset = paginator.paginate_queryset(
                restaurants, request=request, view=self)
                
            serializer = serializers.RestaurantPublicListSerializer(
                paginated_queryset, many=True, context={'request': request})
                
            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "Successfully fetched public restaurant list",
                "data": serializer.data
            }, status=200)
            
            cache.set(cache_key, final_response.data, timeout=60 * 30)
            return final_response

        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong fetching restaurants",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
