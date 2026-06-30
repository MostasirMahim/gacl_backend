from .services.invoices.invoice_payment import process_invoice_payment
from .services.invoices.update_invoice_func import update_invoice
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging
from activity_log.tasks import log_activity_task
from activity_log.utils.functions import request_data_activity_log
from django.db import transaction
from datetime import date
from django.db.models import Prefetch
import pdb
from core.utils.pagination import CustomPageNumberPagination
from django.shortcuts import get_object_or_404
from .models import PaymentMethod, Transaction, Payment, Sale, SaleType, IncomeParticular, IncomeReceivingOption, Income, IncomeReceivingType, MemberAccount, Due, MemberDue, Invoice, InvoiceType, InvoiceItem
from django.utils.http import urlencode
from . import serializers
from .utils.functions import generate_unique_sale_number
from .utils.functions import generate_unique_invoice_number, generate_unique_sale_number
from datetime import datetime
from member.models import Member
import pandas as pd
from django.http import Http404
from .utils.permission_classes import MemberFinancialManagementPermission
logger = logging.getLogger("myapp")


class PaymentMethodView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]
    action_permissions = {
        "GET": "member_financial:view_invoices",
        "POST": "member_financial:adjust_dues",
    }

    def get(self, request):
        try:

            payment_methods = PaymentMethod.objects.filter(is_active=True)
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            serializer = serializers.PaymentMethodSerializer(
                payment_methods, many=True, fields=fields)
            data = serializer.data

            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all payment methods.",
            )

            return Response({
                "code": 200,
                "status": "success",
                "message": "Viewing all payment methods",
                "data": data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="error",
                description="User tried to view payment methods but faced error.",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong.",
                "errors": [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            serializer = serializers.PaymentMethodSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                # Invalidate cache delete
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created a new payment method",
                )

                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "New payment method has been created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="warning",
                    description="User tried to create a new payment method but faced validation error.",
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
                severity_level="error",
                description="User tried to create a new payment method but faced error.",
            )

            return Response({
                "code": 500,
                "status": "failed",
                "message": "Error while creating payment method.",
                "errors": {
                    "server_errors": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class InvoicePaymentView(APIView):
#     permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

#     def post(self, request):
#         try:
#             serializer = serializers.InvoicePaymentSerializer(
#                 data=request.data)
#             if serializer.is_valid():
#                 invoice = serializer.validated_data["invoice_id"]
#                 payment_method = serializer.validated_data["payment_method"]
#                 amount = serializer.validated_data["amount"]
#                 income_particular = serializer.validated_data["income_particular"]
#                 received_from = serializer.validated_data["received_from"]
#                 adjust_from_balance = serializer.validated_data["adjust_from_balance"]
#                 with transaction.atomic():
#                     if amount == invoice.total_amount:
#                         invoice.paid_amount = invoice.total_amount
#                         invoice.is_full_paid = True
#                         invoice.status = "paid"
#                         invoice.balance_due = 0
#                         invoice.save(update_fields=[
#                             "paid_amount", "is_full_paid", "status", "balance_due"])
#                         full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
#                             name="full")
#                         transaction_obj = Transaction.objects.create(
#                             amount=invoice.paid_amount,
#                             transaction_date=date.today(),
#                             status="paid",
#                             member=invoice.member,
#                             invoice=invoice,
#                             payment_method=payment_method
#                         )
#                         Payment.objects.create(
#                             payment_amount=invoice.paid_amount,
#                             payment_status="paid",
#                             payment_date=date.today(),
#                             invoice=invoice,
#                             member=invoice.member,
#                             payment_method=payment_method,
#                             processed_by=request.user,
#                             transaction=transaction_obj
#                         )
#                         sale_type, _ = SaleType.objects.get_or_create(
#                             name=invoice.invoice_type.name)
#                         sale_obj = Sale.objects.create(
#                             sale_number=generate_unique_sale_number(),
#                             sub_total=invoice.total_amount,
#                             total_amount=invoice.paid_amount,
#                             payment_status="paid",
#                             sale_source_type=sale_type,
#                             customer=invoice.member,
#                             payment_method=payment_method,
#                             invoice=invoice
#                         )
#                         Income.objects.create(
#                             receivable_amount=invoice.total_amount,
#                             final_receivable=sale_obj.total_amount,
#                             actual_received=invoice.paid_amount,
#                             reaming_due=0,
#                             particular=income_particular,
#                             received_from_type=received_from,
#                             receiving_type=full_receiving_type,
#                             member=invoice.member,
#                             received_by=payment_method,
#                             sale=sale_obj,
#                             discounted_amount=invoice.discount,
#                             discount_name=invoice.promo_code
#                         )
#                         return Response(
#                             {
#                                 "code": 200,
#                                 "status": "success",
#                                 "message": "Invoice payment successful",
#                                 "data": {
#                                     "invoice_id": invoice.id
#                                 }
#                             }, status=status.HTTP_200_OK
#                         )
#                     elif amount < invoice.total_amount and amount != 0:
#                         payment_amount = amount
#                         if adjust_from_balance:
#                             member_account = MemberAccount.objects.get(
#                                 member=invoice.member)
#                             member_account_balance = member_account.balance
#                             remaining_payment = invoice.total_amount - payment_amount
#                             if member_account_balance >= remaining_payment:
#                                 payment_amount = amount + remaining_payment
#                                 member_account.balance = member_account.balance - remaining_payment
#                                 member_account.save(update_fields=["balance"])
#                             else:
#                                 payment_amount = amount + member_account_balance
#                                 member_account.balance = 0
#                                 member_account.save(update_fields=["balance"])

#                         invoice.paid_amount = payment_amount
#                         if invoice.paid_amount == invoice.total_amount:
#                             invoice.is_full_paid = True
#                             invoice.status = "paid"
#                             invoice.balance_due = 0
#                         else:
#                             invoice.is_full_paid = False
#                             invoice.status = "partial_paid"
#                             invoice.balance_due = invoice.total_amount - invoice.paid_amount
#                         invoice_full_paid = invoice.is_full_paid
#                         invoice_status = invoice.status
#                         invoice_due = invoice.balance_due
#                         invoice.save(update_fields=[
#                             "paid_amount", "is_full_paid", "status", "balance_due"])
#                         if invoice_full_paid:
#                             full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
#                                 name="full")
#                         else:
#                             full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
#                                 name="partial")
#                         transaction_obj = Transaction.objects.create(
#                             amount=amount,
#                             transaction_date=date.today(),
#                             status=invoice_status,
#                             member=invoice.member,
#                             invoice=invoice,
#                             payment_method=payment_method
#                         )
#                         payment_obj = Payment.objects.create(
#                             payment_amount=amount,
#                             payment_status=invoice_status,
#                             payment_date=date.today(),
#                             invoice=invoice,
#                             member=invoice.member,
#                             payment_method=payment_method,
#                             processed_by=request.user,
#                             transaction=transaction_obj
#                         )
#                         sale_type, _ = SaleType.objects.get_or_create(
#                             name=invoice.invoice_type.name)
#                         sale_obj = Sale.objects.create(
#                             sale_number=generate_unique_sale_number(),
#                             sub_total=invoice.total_amount,
#                             total_amount=invoice.paid_amount,
#                             payment_status=invoice_status,
#                             sale_source_type=sale_type,
#                             customer=invoice.member,
#                             payment_method=payment_method,
#                             invoice=invoice,
#                             due_date=date.today()
#                         )
#                         Income.objects.create(
#                             receivable_amount=invoice.total_amount,
#                             final_receivable=sale_obj.total_amount,
#                             actual_received=amount,
#                             reaming_due=invoice_due,
#                             particular=income_particular,
#                             received_from_type=received_from,
#                             receiving_type=full_receiving_type,
#                             member=invoice.member,
#                             received_by=payment_method,
#                             sale=sale_obj,
#                             discounted_amount=invoice.discount,
#                             discount_name=invoice.promo_code
#                         )
#                         due_obj = Due.objects.create(
#                             original_amount=invoice.total_amount,
#                             due_amount=invoice_due,
#                             paid_amount=payment_amount,
#                             due_date=date.today(),
#                             member=invoice.member,
#                             invoice=invoice,
#                             payment=payment_obj,
#                             transaction=transaction_obj
#                         )
#                         MemberDue.objects.create(
#                             amount_due=due_obj.due_amount,
#                             due_date=date.today(),
#                             amount_paid=due_obj.paid_amount,
#                             payment_date=date.today(),
#                             member=invoice.member,
#                             due_reference=due_obj
#                         )
#                         log_activity_task.delay_on_commit(
#                             request_data_activity_log(request),
#                             verb="Creation",
#                             severity_level="info",
#                             description="User paid an invoice",
#                         )
#                         return Response(
#                             {
#                                 "code": 200,
#                                 "status": "success",
#                                 "message": "Invoice payment successful",
#                                 "data": {
#                                     "invoice_id": invoice.id
#                                 }
#                             }, status=status.HTTP_200_OK
#                         )
#                     else:
#                         payment_amount = 0
#                         if adjust_from_balance:
#                             member_account = MemberAccount.objects.get(
#                                 member=invoice.member)
#                             member_account_balance = member_account.balance
#                             if member_account_balance >= invoice.total_amount:
#                                 payment_amount = invoice.total_amount
#                                 member_account.balance = member_account_balance - invoice.total_amount
#                                 invoice.is_full_paid = True
#                                 invoice.status = "paid"
#                                 invoice.balance_due = 0
#                             else:
#                                 payment_amount = member_account_balance
#                                 member_account.balance = 0
#                                 invoice.is_full_paid = False
#                                 invoice.balance_due = invoice.total_amount - payment_amount
#                                 if payment_amount != 0:
#                                     invoice.status = "partial_paid"
#                                 else:
#                                     invoice.status = "due"
#                         member_account.save(update_fields=["balance"])
#                         invoice.paid_amount = payment_amount
#                         invoice_status = invoice.status
#                         invoice_is_full_paid = invoice.is_full_paid
#                         invoice.save(update_fields=[
#                             "paid_amount", "is_full_paid", "status", "balance_due"])
#                         if invoice_is_full_paid:
#                             full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
#                                 name="full")
#                         else:
#                             full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
#                                 name="partial")

#                         transaction_obj = Transaction.objects.create(
#                             amount=payment_amount,
#                             transaction_date=date.today(),
#                             status=invoice_status,
#                             member=invoice.member,
#                             invoice=invoice,
#                             payment_method=payment_method
#                         )
#                         payment_obj = Payment.objects.create(
#                             payment_amount=payment_amount,
#                             payment_status=invoice_status,
#                             payment_date=date.today(),
#                             invoice=invoice,
#                             member=invoice.member,
#                             payment_method=payment_method,
#                             processed_by=request.user,
#                             transaction=transaction_obj
#                         )
#                         sale_type, _ = SaleType.objects.get_or_create(
#                             name=invoice.invoice_type.name)
#                         sale_obj = Sale.objects.create(
#                             sale_number=generate_unique_sale_number(),
#                             sub_total=invoice.total_amount,
#                             total_amount=invoice.paid_amount,
#                             payment_status=invoice_status,
#                             sale_source_type=sale_type,
#                             customer=invoice.member,
#                             payment_method=payment_method,
#                             invoice=invoice,
#                             due_date=date.today()
#                         )
#                         Income.objects.create(
#                             receivable_amount=invoice.total_amount,
#                             final_receivable=sale_obj.total_amount,
#                             actual_received=invoice.paid_amount,
#                             reaming_due=invoice.balance_due,
#                             particular=income_particular,
#                             received_from_type=received_from,
#                             receiving_type=full_receiving_type,
#                             member=invoice.member,
#                             received_by=payment_method,
#                             sale=sale_obj,
#                             discounted_amount=invoice.discount,
#                             discount_name=invoice.promo_code
#                         )
#                         due_obj = Due.objects.create(
#                             original_amount=invoice.total_amount,
#                             due_amount=invoice.balance_due,
#                             paid_amount=invoice.paid_amount,
#                             due_date=date.today(),
#                             member=invoice.member,
#                             invoice=invoice,
#                             payment=payment_obj,
#                             transaction=transaction_obj
#                         )
#                         MemberDue.objects.create(
#                             amount_due=due_obj.due_amount,
#                             due_date=date.today(),
#                             amount_paid=due_obj.paid_amount,
#                             payment_date=date.today(),
#                             member=invoice.member,
#                             due_reference=due_obj
#                         )
#                         log_activity_task.delay_on_commit(
#                             request_data_activity_log(request),
#                             verb="Creation",
#                             severity_level="info",
#                             description="User paid an invoice",
#                         )
#                         return Response(
#                             {
#                                 "code": 200,
#                                 "status": "success",
#                                 "message": "Invoice payment successful",
#                                 "data": {
#                                     "invoice_id": invoice.id
#                                 }
#                             }, status=status.HTTP_200_OK
#                         )

#             else:
#                 log_activity_task.delay_on_commit(
#                     request_data_activity_log(request),
#                     verb="Creation",
#                     severity_level="info",
#                     description="User tried to pay an invoice but faced an error",
#                 )
#                 return Response({
#                     "code": 400,
#                     "status": "failed",
#                     "message": "Bad request",
#                     "errors": serializer.errors
#                 }, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.exception(str(e))
#             log_activity_task.delay_on_commit(
#                 request_data_activity_log(request),
#                 verb="Creation",
#                 severity_level="info",
#                 description="User tried to pay an invoice but faced an error",
#             )
#             return Response({
#                 "code": 500,
#                 "status": "failed",
#                 "message": "Something went wrong.",
#                 "errors": {
#                     "server_error": [str(e)]
#                 }
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InvoicePaymentView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        serializer = serializers.InvoicePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = serializer.validated_data["invoice_id"]
        payment_method = serializer.validated_data["payment_method"]
        amount = serializer.validated_data["amount"]
        income_particular = serializer.validated_data["income_particular"]
        received_from = serializer.validated_data["received_from"]
        adjust_from_balance = serializer.validated_data["adjust_from_balance"]

        result = process_invoice_payment(
            invoice,
            payment_method,
            amount,
            income_particular,
            received_from,
            adjust_from_balance,
            request.user,
            request,
        )

        if result["status"] == "success":
            return Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Invoice payment successful",
                    "data": {"invoice_id": result["invoice_id"]},
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "code": 500,
                    "status": "failed",
                    "message": "Something went wrong",
                    "errors": {"server_error": [result["error"]]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IncomeParticularView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            serializer = serializers.IncomeParticularSerializer(
                data=request.data)
            if serializer.is_valid():
                cache.delete("active_income_particulars")  # Invalidate cache
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created an Income particular",
                )
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "New income particular created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User tried to create an Income particular but faced error",
                )
                return Response({
                    "code": 400,
                    "status": "success",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User tried to create an Income particular but faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_errors": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:

            income_particular = IncomeParticular.objects.filter(
                is_active=True)
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            serializer = serializers.IncomeParticularSerializer(
                income_particular, many=True, fields=fields)
            data = serializer.data

            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all income particulars",
            )
            return Response({
                "code": 200,
                "status": "success",
                "message": "list of all income particulars",
                "data": data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to create an Income particular but faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncomeReceivedFromView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            serializer = serializers.IncomeReceivingOptionSerializer(
                data=request.data)
            if serializer.is_valid():
                # Invalidate cache
                cache.delete("active_income_receiving_options")
                serializer.save()
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User created and Income received from option",
                )
                return Response({
                    "code": 201,
                    "status": "success",
                    "message": "New income receiving option created",
                    "data": serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Creation",
                    severity_level="info",
                    description="User requested to create Income received from option and faced and error",
                )
                return Response({
                    "code": 400,
                    "status": "success",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Creation",
                severity_level="info",
                description="User requested to create Income received from option and faced and error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_errors": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            # implement caching

            data = IncomeReceivingOption.objects.filter(is_active=True)
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            serializer = serializers.IncomeReceivingOptionSerializer(
                data, many=True, fields=fields)
            data = serializer.data

            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all income received from view list",
            )
            return Response({
                "code": 200,
                "status": "success",
                "message": "list of all income receiving option",
                "data": data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all income received from but faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceShowView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            # hit db if miss
            queryset = Invoice.active_objects.select_related(
                "invoice_type", "generated_by", "member", "restaurant", "event"
            ).prefetch_related(
                Prefetch("invoice_items__restaurant_items"),
                Prefetch("invoice_items__products"),
                Prefetch("invoice_items__facility"),
                Prefetch("invoice_items__event_tickets"),
            ).order_by("-id")
            # fields query param
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None

            # get query params
            is_full_paid = self.request.query_params.get("is_full_paid")
            invoice_type = self.request.query_params.get("invoice_type")
            member_id = self.request.query_params.get("member")
            status_name = self.request.query_params.get("status")

            # apply filters if query params are present
            if is_full_paid is not None:
                queryset = queryset.filter(
                    is_full_paid=is_full_paid.lower() == "true")

            if invoice_type is not None:
                queryset = queryset.filter(
                    invoice_type__name__iexact=invoice_type.lower())
            if member_id is not None:
                queryset = queryset.filter(member__member_ID=member_id)
            if status_name is not None:
                queryset = queryset.filter(status__iexact=status_name)

            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                queryset, request, view=self)
            serializer = serializers.InvoiceForViewSerializer(
                paginated_queryset, many=True, fields=fields)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all invoices",
            )
            final_response = paginator.get_paginated_response({
                "code": 200,
                "status": "success",
                "message": "List of all invoices",
                "data": serializer.data
            }, status=200)
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view all invoices but faced an error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        try:
            serializer = serializers.InvoiceDeleteSerializer(data=request.data)
            if serializer.is_valid():
                invoice_ids = serializer.data["invoice_id"]
                with transaction.atomic():
                    invoices = Invoice.active_objects.filter(
                        pk__in=invoice_ids)
                    invoices.all().update(is_active=False)
                    invoices = Invoice.objects.prefetch_related(
                        "transaction_invoice", "payment_invoice", "sale_invoice", "due_invoice", "invoice_items", "due_invoice__member_due_due_reference").select_for_update().filter(pk__in=invoice_ids)
                    for invoice in invoices:
                        Transaction.objects.filter(
                            invoice=invoice).update(is_active=False)
                        Payment.objects.filter(
                            invoice=invoice).update(is_active=False)
                        Sale.objects.filter(
                            invoice=invoice).update(is_active=False)
                        Due.objects.filter(invoice=invoice).update(
                            is_active=False)
                        InvoiceItem.objects.filter(
                            invoice=invoice).update(is_active=False)
                        for due in invoice.due_invoice.all():
                            MemberDue.objects.filter(
                                due_reference=due).update(is_active=False)
                        for sale in invoice.sale_invoice.all():
                            Income.objects.filter(
                                sale=sale).update(is_active=False)
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="delete",
                    severity_level="info",
                    description="user deleted some invoices invoice",
                )
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Invoices deleted successfully",
                    "data": invoice_ids
                }, status=200)
            else:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request",
                    "errors": serializer.errors
                }, status=400)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="delete",
                severity_level="info",
                description="user tried to delete a single invoice and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:
            queryset = get_object_or_404(Invoice.active_objects.select_related(
                "invoice_type", "generated_by", "member", "restaurant", "event"
            ).prefetch_related(
                Prefetch("invoice_items__restaurant_items"),
                Prefetch("invoice_items__products"),
                Prefetch("invoice_items__facility"),
                Prefetch("invoice_items__event_tickets"),
            ), pk=id)
            serializer = serializers.InvoiceForViewSerializer(
                queryset)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a single invoice",
            )
            return Response({
                "code": 200,
                "status": "success",
                "message": "Viewing a single invoice",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a single invoice and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, id):
        try:
            with transaction.atomic():
                try:
                    invoice = Invoice.active_objects.prefetch_related(
                        "transaction_invoice", "payment_invoice", "sale_invoice", "due_invoice",
                        "invoice_items", "due_invoice__member_due_due_reference"
                    ).select_for_update().get(pk=id)
                except Invoice.DoesNotExist:
                    raise Http404("Invoice does not exist for this id")

                invoice.is_active = False
                invoice.save(update_fields=["is_active"])
                invoice.transaction_invoice.all().update(is_active=False)
                invoice.payment_invoice.all().update(is_active=False)
                invoice.sale_invoice.all().update(is_active=False)
                invoice.due_invoice.all().update(is_active=False)
                invoice.invoice_items.all().update(is_active=False)

                for due in invoice.due_invoice.all():
                    MemberDue.objects.filter(
                        due_reference=due).update(is_active=False)

                for sale in invoice.sale_invoice.all():
                    Income.objects.filter(sale=sale).update(is_active=False)

                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="delete",
                    severity_level="info",
                    description="user deleted a single invoice",
                )
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Invoice deleted successfully",
                    "data": {
                        "invoice": id
                    }
                }, status=200)

        except Http404 as e:
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Invoice not found",
                "errors": {
                    "invoice": [str(e)]
                }
            }, status=404)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="delete",
                severity_level="error",
                description="user tried to delete a single invoice and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # def patch(self, request, id):
    #     try:
    #         is_exist = Invoice.active_objects.filter(pk=id).exists()
    #         if not is_exist:
    #             return Response({
    #                 "code": 404,
    #                 "status": "failed",
    #                 "message": "No invoice found with this id.",
    #                 "errors": {
    #                     "invoice": ["No invoice found with this id."]
    #                 }
    #             }, status=404)
    #         serializer = serializers.InvoiceUpdateSerializer(data=request.data)
    #         if serializer.is_valid():
    #             paid_amount = serializer.validated_data["paid_amount"]
    #             payment_method = serializer.validated_data["payment_method"]
    #             with transaction.atomic():
    #                 invoice = Invoice.active_objects.get(pk=id)
    #                 if invoice.status == "paid":
    #                     invoice.balance_due = invoice.total_amount - paid_amount
    #                     invoice.total_amount = total_amount
    #                     invoice.paid_amount = paid_amount
    #                     invoice.save(update_fields=[
    #                                  "balance_due", "total_amount", "paid_amount"])
    #                     log_activity_task.delay_on_commit(
    #                         request_data_activity_log(request),
    #                         verb="Update",
    #                         severity_level="info",
    #                         description="User Updated an invoice. ",
    #                     )
    #                     return Response({
    #                         "code": 200,
    #                         "status": "success",
    #                         "message": "Invoice updated successfully",
    #                         "data": serializers.InvoiceForViewSerializer(invoice).data
    #                     }, status=200)

    #                 full_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
    #                     name="full")
    #                 partial_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
    #                     name="partial")
    #                 paid_amount = invoice.paid_amount
    #                 total_amount = invoice.total_amount
    #                 due_amount = invoice.balance_due
    #                 if paid_amount == total_amount:
    #                     income_receiving_type = full_income_receiving_type
    #                 else:
    #                     income_receiving_type = partial_income_receiving_type
    #                 invoice.balance_due = due_amount
    #                 invoice.paid_amount = paid_amount
    #                 invoice.total_amount = total_amount
    #                 if total_amount == paid_amount:
    #                     invoice.status = "paid"
    #                 else:
    #                     invoice.status = invoice.status
    #                 invoice.save(update_fields=[
    #                              "balance_due", "paid_amount", "total_amount", "status"])
    #                 Transaction.objects.filter(
    #                     invoice=invoice).update(is_active=False)
    #                 transaction_obj = Transaction.objects.create(
    #                     amount=invoice.paid_amount,
    #                     member=invoice.member,
    #                     invoice=invoice,
    #                     payment_method=payment_method,
    #                     notes="The transaction has been made after updating an invoice."
    #                 )
    #                 Payment.objects.filter(
    #                     invoice=invoice).update(is_active=False)
    #                 payment_obj = Payment.objects.create(
    #                     payment_amount=paid_amount,
    #                     payment_status=invoice.status,
    #                     notes="This payment has been made after updating an invoice.",
    #                     transaction=transaction_obj,
    #                     invoice=invoice,
    #                     member=invoice.member,
    #                     payment_method=payment_method,
    #                     processed_by=request.user
    #                 )
    #                 due_date = datetime.today()
    #                 old_sale_ref = Sale.active_objects.select_related(
    #                     "sale_source_type").filter(invoice=invoice).first()
    #                 sale_type = old_sale_ref.sale_source_type
    #                 Sale.objects.filter(
    #                     invoice=invoice).update(is_active=False)
    #                 sale_obj = Sale.objects.create(sale_number=generate_unique_sale_number(),
    #                                                sub_total=invoice.total_amount,
    #                                                total_amount=invoice.total_amount,
    #                                                payment_status=invoice.status,
    #                                                due_date=due_date,
    #                                                notes="This sale has been created after updating an invoice.",
    #                                                sale_source_type=sale_type,
    #                                                customer=invoice.member,
    #                                                payment_method=payment_method,
    #                                                invoice=invoice
    #                                                )
    #                 old_income_ref = Income.objects.select_related(
    #                     "particular", "received_from_type").filter(sale=old_sale_ref).first()
    #                 income_particular = old_income_ref.particular
    #                 received_from = old_income_ref.received_from_type
    #                 Income.objects.filter(
    #                     sale=old_sale_ref).update(is_active=False)
    #                 Income.objects.create(
    #                     receivable_amount=invoice.total_amount,
    #                     final_receivable=invoice.total_amount,
    #                     actual_received=invoice.paid_amount,
    #                     reaming_due=invoice.balance_due,
    #                     particular=income_particular,
    #                     received_from_type=received_from,
    #                     member=invoice.member,
    #                     received_by=payment_method,
    #                     sale=sale_obj,
    #                     receiving_type=income_receiving_type)
    #                 Due.objects.filter(
    #                     invoice=invoice).update(is_active=False)
    #                 old_due_ref = Due.objects.filter(invoice=invoice).first()
    #                 MemberDue.objects.filter(
    #                     due_reference=old_due_ref).update(is_active=False)
    #                 if due_amount > 0:  # it has due
    #                     due_obj = Due.objects.create(
    #                         original_amount=invoice.total_amount,
    #                         due_amount=invoice.balance_due,
    #                         paid_amount=invoice.paid_amount,
    #                         due_date=datetime.today(),
    #                         payment_status=invoice.status,
    #                         member=invoice.member,
    #                         invoice=invoice,
    #                         payment=payment_obj,
    #                         transaction=transaction_obj,
    #                     )
    #                     MemberDue.objects.create(
    #                         amount_due=due_obj.due_amount,
    #                         due_date=datetime.today(),
    #                         amount_paid=invoice.paid_amount,
    #                         payment_date=datetime.today(),
    #                         notes="This due has been created when a invoice was updated.",
    #                         member=invoice.member,
    #                         due_reference=due_obj
    #                     )
    #                 log_activity_task.delay_on_commit(
    #                     request_data_activity_log(request),
    #                     verb="Update",
    #                     severity_level="info",
    #                     description="User Updated an invoice. ",
    #                 )
    #                 return Response({
    #                     "code": 200,
    #                     "status": "success",
    #                     "message": "Invoice updated successfully",
    #                     "data": serializers.InvoiceForViewSerializer(invoice).data
    #                 }, status=200)
    #         else:
    #             return Response({
    #                 "code": 400,
    #                 "status": "failed",
    #                 "message": "Bad request.",
    #                 "errors": serializer.errors
    #             }, status=404)

    #     except Exception as e:
    #         logger.exception(str(e))
    #         log_activity_task.delay_on_commit(
    #             request_data_activity_log(request),
    #             verb="Update",
    #             severity_level="info",
    #             description="User Updated an invoice and faced an error. ",
    #         )
    #         return Response({
    #             "code": 500,
    #             "status": "failed",
    #             "message": "Something went wrong",
    #             "errors": {
    #                 "server_error": [str(e)]
    #             }
    #         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, id):
        try:
            # Validate incoming data
            serializer = serializers.InvoiceUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Bad request.",
                    "errors": serializer.errors
                }, status=400)

            # Call the service function
            result = update_invoice(
                invoice_id=id,
                validated_data=serializer.validated_data,
                user=request.user,
                request=request
            )

            # Handle service response
            if result.get("status") == "success":
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Invoice updated successfully",
                    "data": serializers.InvoiceForViewSerializer(result["invoice"]).data
                }, status=200)

            elif result.get("status") == "error":
                return Response({
                    "code": 500,
                    "status": "failed",
                    "message": "Something went wrong",
                    "errors": {"server_error": [result.get("error")]}
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            else:  # Not found
                return Response(result, status=404)

        except Exception as e:
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Server error",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceCustomDeleteView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def delete(self, request):
        try:
            serializer = serializers.InvoiceCustomDeleteSerializer(
                data=request.data)
            if serializer.is_valid():
                issued_date = serializer.validated_data["issued_date"]
                invoice_type = serializer.validated_data["invoice_type"]
                filters = {}
                if issued_date is not None:
                    filters["issue_date"] = issued_date
                if invoice_type is not None:
                    filters["invoice_type__name"] = invoice_type
                with transaction.atomic():
                    invoices = Invoice.active_objects.filter(**filters)
                    deleted_count = invoices.all().update(is_active=False)
                    invoices = Invoice.objects.prefetch_related(
                        "transaction_invoice", "payment_invoice", "sale_invoice", "due_invoice", "invoice_items", "due_invoice__member_due_due_reference").select_for_update().filter(**filters)
                    for invoice in invoices:
                        invoice.transaction_invoice.all().update(is_active=False)
                        invoice.payment_invoice.all().update(is_active=False)
                        invoice.sale_invoice.all().update(is_active=False)
                        invoice.due_invoice.all().update(is_active=False)
                        invoice.invoice_items.all().update(is_active=False)
                        for due in invoice.due_invoice.all():
                            MemberDue.objects.filter(
                                due_reference=due).update(is_active=False)
                        for sale in invoice.sale_invoice.all():
                            Income.objects.filter(
                                sale=sale).update(is_active=False)

                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Invoices deleted based on custom filtering",
                    "data": {
                        "delete_count": deleted_count
                    }
                }, status=200)
            else:
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Something went wrong",
                    "errors": serializer.errors
                }, status=400)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Delete",
                severity_level="info",
                description="User tried to delete some invoices based on custom filtering but faced an error. ",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncomeView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            data = Income.active_objects.filter(is_active=True).select_related(
                "particular", "received_from_type", "receiving_type", "member", "received_by", "sale").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.IncomeSerializer(
                paginated_queryset, many=True)
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all income",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a single invoice and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncomeSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            queryset = Income.objects.select_related(
                "sale", "particular", "received_from_type", "receiving_type", "member", "received_by").filter(is_active=True).order_by("id")
            queryset = get_object_or_404(queryset, pk=id)
            serializer = serializers.IncomeSpecificSerializer(
                queryset)
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all income",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a single invoice and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            # hit db if miss
            data = Sale.active_objects.filter(is_active=True).select_related(
                "sale_source_type", "customer", "invoice").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.SaleSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all sales",
            )
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all sales",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view list of sales and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            data = get_object_or_404(Sale.active_objects.select_related(
                "sale_source_type", "customer", "payment_method"), pk=id)
            serializer = serializers.SaleSpecificSerializer(
                data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a sale",
            )
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the specific sale",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a sale and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransactionView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            data = Transaction.active_objects.select_related(
                "member", "invoice", "payment_method").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.TransactionSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all transaction",
            )
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all transaction",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view list of transaction and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransactionSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            data = get_object_or_404(Transaction.active_objects.select_related(
                "member", "invoice", "payment_method", "invoice__invoice_type", "invoice__generated_by", "invoice__member", "invoice__restaurant", "invoice__event"), pk=id)
            serializer = serializers.TransactionSpecificSerializer(
                data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a transaction",
            )
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the a specific transaction",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a transaction and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            # hit db if miss
            data = Payment.active_objects.select_related(
                "invoice", "member", "payment_method", "processed_by", "transaction").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.PaymentSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all payments",
            )
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all payments",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view list of payments and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            data = get_object_or_404(Payment.active_objects.select_related(
                "invoice", "member", "payment_method", "processed_by", "transaction", "invoice__invoice_type",
                "invoice__generated_by",
                "invoice__member",
                "invoice__restaurant",
                "invoice__event",
                "transaction__member",
                "transaction__invoice",
                "transaction__payment_method"
            ), pk=id)
            serializer = serializers.PaymentSpecificSerializer(
                data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a payment",
            )
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the a specific payment",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a payment and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DueView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            data = Due.active_objects.select_related(
                "member", "invoice", "payment", "transaction").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.DuesSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all Dues",
            )
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all dues",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view list of dues and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DueSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            data = get_object_or_404(Due.active_objects.select_related(
                "member", "invoice", "payment", "transaction", "invoice__invoice_type",
                "invoice__generated_by",
                "invoice__member",
                "invoice__restaurant",
                "invoice__event",
                "transaction__member",
                "transaction__invoice",
                "transaction__payment_method",
                "payment__invoice",
                "payment__member",
                "payment__payment_method",
                "payment__transaction",
                "payment__processed_by",
            ), pk=id)
            serializer = serializers.DuesSpecificSerializer(
                data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a due",
            )
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing a specific due",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a due and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberDueView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            data = MemberDue.active_objects.select_related(
                "member", "due_reference").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.MemberDueSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all member dues",
            )
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all member dues",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view list of member dues and faced error",
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
            serializer = serializers.MemberDuePaymentSerializer(
                data=request.data)
            if serializer.is_valid():
                member_due = serializer.validated_data["member_due_id"]
                payment_method = serializer.validated_data["payment_method"]
                amount = serializer.validated_data["amount"]
                adjust_from_balance = serializer.validated_data["adjust_from_balance"]
                due = member_due.due_reference
                invoice = due.invoice
                # pdb.set_trace()
                sale = Sale.objects.prefetch_related("income_sale").get(
                    invoice=invoice)
                income = sale.income_sale.first()
                due_amount = member_due.amount_due
                with transaction.atomic():

                    if amount == due_amount:
                        full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                            name="full")
                        invoice.balance_due = 0
                        invoice.paid_amount += amount
                        invoice.is_full_paid = True
                        invoice.status = "paid"
                        invoice.save(update_fields=[
                                     "balance_due", "paid_amount", "is_full_paid", "status"])
                        transaction_obj = Transaction.objects.create(
                            amount=amount,
                            status="full_paid",
                            member=invoice.member,
                            invoice=invoice,
                            payment_method=payment_method
                        )
                        Payment.objects.create(
                            payment_amount=amount,
                            payment_status="paid",
                            invoice=invoice,
                            member=invoice.member,
                            payment_method=payment_method,
                            processed_by=request.user,
                            transaction=transaction_obj
                        )
                        # update Due table
                        due.due_amount = 0
                        due.paid_amount += amount
                        due.last_payment_date = date.today()
                        due.is_due_paid = True
                        due.transaction = transaction_obj
                        due.save(update_fields=[
                                 "due_amount", "paid_amount", "last_payment_date", "is_due_paid", "transaction"])

                        # update member due table
                        member_due.amount_due = 0
                        member_due.amount_paid += amount
                        member_due.payment_date = date.today()
                        member_due.is_due_paid = True
                        member_due.save(
                            update_fields=["amount_due", "amount_paid", "payment_date", "is_due_paid"])
                        # add data to income table
                        Income.objects.create(
                            receivable_amount=invoice.total_amount,
                            final_receivable=amount,
                            actual_received=amount,
                            reaming_due=0,
                            particular=income.particular,
                            received_from_type=income.received_from_type,
                            receiving_type=full_receiving_type,
                            member=invoice.member,
                            received_by=payment_method,
                            sale=sale
                        )
                        return Response({
                            "code": 200,
                            "status": "success",
                            "message": "Due paid successfully",
                            "data": {
                                "member_due": member_due.id
                            }
                        }, status=status.HTTP_200_OK)
                    else:

                        if adjust_from_balance:
                            member_account = MemberAccount.objects.get(
                                member=member_due.member)
                            member_account_balance = member_account.balance
                            if member_account_balance >= due_amount:
                                amount = due_amount
                                member_account.balance = member_account_balance - amount
                            else:
                                remaining_amount = due_amount-amount
                                if remaining_amount >= member_account_balance:
                                    amount += remaining_amount
                                    member_account.balance -= remaining_amount
                                else:
                                    amount += member_account_balance
                                    member_account.balance = 0
                            member_account.save(update_fields=["balance"])

                        if amount == due_amount:
                            full_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                                name="full")
                            invoice.balance_due = 0
                            invoice.paid_amount += amount
                            invoice.is_full_paid = True
                            invoice.status = "paid"
                            invoice.save(update_fields=[
                                "balance_due", "paid_amount", "is_full_paid", "status"])
                            transaction_obj = Transaction.objects.create(
                                amount=amount,
                                status="full_paid",
                                member=invoice.member,
                                invoice=invoice,
                                payment_method=payment_method
                            )
                            Payment.objects.create(
                                payment_amount=amount,
                                payment_status="paid",
                                invoice=invoice,
                                member=invoice.member,
                                payment_method=payment_method,
                                processed_by=request.user,
                                transaction=transaction_obj
                            )
                            # update Due table
                            due.due_amount = 0
                            due.paid_amount += amount
                            due.last_payment_date = date.today()
                            due.is_due_paid = True
                            due.transaction = transaction_obj
                            due.save(update_fields=[
                                "due_amount", "paid_amount", "last_payment_date", "is_due_paid", "transaction"])

                            # update member due table
                            member_due.amount_due = 0
                            member_due.amount_paid += amount
                            member_due.payment_date = date.today()
                            member_due.is_due_paid = True
                            member_due.save(
                                update_fields=["amount_due", "amount_paid", "payment_date", "is_due_paid"])
                            # add data to income table
                            Income.objects.create(
                                receivable_amount=invoice.total_amount,
                                final_receivable=amount,
                                actual_received=amount,
                                reaming_due=0,
                                particular=income.particular,
                                received_from_type=income.received_from_type,
                                receiving_type=full_receiving_type,
                                member=invoice.member,
                                received_by=payment_method,
                                sale=sale
                            )
                        else:
                            partial_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                                name="partial")
                            invoice.balance_due -= amount
                            invoice.paid_amount += amount
                            invoice.is_full_paid = False
                            invoice.status = "due"
                            invoice.save(update_fields=[
                                "balance_due", "paid_amount", "is_full_paid", "status"])
                            transaction_obj = Transaction.objects.create(
                                amount=amount,
                                status="partial_paid",
                                member=invoice.member,
                                invoice=invoice,
                                payment_method=payment_method
                            )
                            Payment.objects.create(
                                payment_amount=amount,
                                payment_status="due",
                                invoice=invoice,
                                member=invoice.member,
                                payment_method=payment_method,
                                processed_by=request.user,
                                transaction=transaction_obj
                            )
                            # update Due table
                            due.due_amount -= amount
                            due.paid_amount += amount
                            due.last_payment_date = date.today()
                            due.is_due_paid = False
                            due.transaction = transaction_obj
                            due.save(update_fields=[
                                "due_amount", "paid_amount", "last_payment_date", "is_due_paid", "transaction"])

                            # update member due table
                            member_due.amount_due -= amount
                            member_due.amount_paid += amount
                            member_due.payment_date = date.today()
                            member_due.is_due_paid = False
                            member_due.save(
                                update_fields=["amount_due", "amount_paid", "payment_date", "is_due_paid"])
                            # add data to income table
                            Income.objects.create(
                                receivable_amount=invoice.total_amount,
                                final_receivable=amount,
                                actual_received=amount,
                                reaming_due=member_due.amount_due,
                                particular=income.particular,
                                received_from_type=income.received_from_type,
                                receiving_type=partial_receiving_type,
                                member=invoice.member,
                                received_by=payment_method,
                                sale=sale
                            )
                    return Response({
                        "code": 200,
                        "status": "success",
                        "message": "Due paid successfully",
                        "data": {
                            "member_due": member_due.id
                        }
                    }, status=status.HTTP_200_OK)
            else:
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
                verb="View",
                severity_level="info",
                description="User tried to view a member due and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberDueSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            data = get_object_or_404(MemberDue.active_objects.select_related(
                "member", "due_reference", "due_reference__invoice",
                "due_reference__member", "due_reference__payment", "due_reference__transaction", "due_reference__transaction"), pk=id)
            serializer = serializers.MemberDueSpecificSerializer(
                data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a member due",
            )
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing a specific member due",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a member due and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberAccountView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request):
        try:

            data = MemberAccount.active_objects.select_related(
                "member").order_by("-id")
            paginator = CustomPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(
                data, request=request, view=self)
            serializer = serializers.MemberAccountSerializer(
                paginated_queryset, many=True)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed all member accounts",
            )
            final_response = paginator.get_paginated_response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing the list of all member accounts",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view list of member accounts and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberAccountSpecificSpecificView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def get(self, request, id):
        try:

            data = get_object_or_404(MemberAccount.active_objects.select_related(
                "member"), member__member_ID=id)
            serializer = serializers.MemberAccountSerializer(
                data)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User viewed a member account",
            )
            final_response = Response(
                {
                    "code": 200,
                    "status": "success",
                    "message": "Viewing a specific member account",
                    "data": serializer.data
                }, status=status.HTTP_200_OK
            )
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View",
                severity_level="info",
                description="User tried to view a member account and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MemberAccountRechargeView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            data = request.data
            serializer = serializers.MemberAccountRechargeSerializer(data=data)
            if serializer.is_valid():
                member_ID = serializer.validated_data["member_ID"]
                amount = serializer.validated_data["amount"]
                with transaction.atomic():
                    member_account = MemberAccount.objects.get(
                        member__member_ID=member_ID)
                    member_account.balance += amount
                    member_account.save(update_fields=["balance"])

                    return Response({
                        "code": 200,
                        "status": "success",
                        "message": "Member account balance recharged successfully",
                        "data": {

                            "member_ID": member_ID,
                            "amount": amount,
                        }
                    }, status=status.HTTP_200_OK)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="View",
                    severity_level="info",
                    description="User tried to recharge a member account and faced error",
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
                verb="View",
                severity_level="info",
                description="User tried to recharge a member account and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoungeUploadExcelView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            serializer = serializers.LoungeUploadExcelSerializer(
                data=request.data)
            if serializer.is_valid():
                excel_file = serializer.validated_data["excel_file"]
                uploaded_file = excel_file
                file_data_cl = None
                try:

                    if uploaded_file.name.endswith('.xlsx'):
                        file_data_cl = pd.read_excel(
                            uploaded_file, engine='openpyxl', dtype=str)
                    elif uploaded_file.name.endswith('.xls'):
                        file_data_cl = pd.read_excel(
                            uploaded_file, engine='xlrd', dtype=str)
                    # Extract and format the date range
                    pick_date = file_data_cl.iat[1, 0]
                    if isinstance(pick_date, str):
                        date_data = pick_date.strip().split(": ")[1]
                        lng_date = datetime.strptime(
                            date_data, "%d.%m.%y").strftime("%Y-%m-%d")

                        sales_date = datetime.strptime(
                            date_data, "%d.%m.%y").date()
                    else:
                        return Response({
                            "code": 400,
                            "status": "failed",
                            "message": "Invalid date format",
                            "errors": {
                                "pick_date": [f"Error: Expected a string, but got {type(pick_date)}. Value: {pick_date}"]
                            }
                        }, status=400)

                    if file_data_cl is not None:
                        file_data_cl = file_data_cl.dropna(how='all')

                        # Select relevant columns and rename them
                        file_data_cl = file_data_cl[['Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3',
                                                    'Unnamed: 4', 'Unnamed: 5']]  # total 5 columns

                        file_data_cl.columns = [
                            'member_ID', 'cash_amount', 'card_amount', 'due_amount', 'total']

                        file_data_cl = file_data_cl.iloc[3:-
                                                         1].reset_index(drop=True)

                        # Convert numeric columns
                        numeric_columns = ['cash_amount',
                                           'card_amount', 'due_amount', 'total']
                        file_data_cl[numeric_columns] = file_data_cl[numeric_columns].apply(
                            pd.to_numeric, errors='coerce').fillna(0)

                        # Calculate totals
                        totals = {col: int(file_data_cl[col].sum())
                                  for col in numeric_columns}

                        totals['cash_amount'] = int(totals['cash_amount'])
                        totals['card_amount'] = int(totals['card_amount'])
                        totals['due_amount'] = int(totals['due_amount'])
                        totals['total'] = int(totals['total'])
                except Exception as e:
                    return Response({
                        "code": 400,
                        "status": "failed",
                        "message": "Invalid excel file",
                        "errors": {
                            "excel_file": ["There was an error while reading excel file. Please check if you have uploaded the correct file."]
                        }
                    }, status=400)

                data = file_data_cl.to_dict(orient='records')
                income_particular = serializer.validated_data["income_particular"]
                received_from = serializer.validated_data["received_from"]
                confirm_reupload = serializer.validated_data["confirm_reupload"]
                if not confirm_reupload:
                    if len(data) >= 1:
                        single_record = data[0]
                        single_member_ID = single_record["member_ID"]
                        single_cash_amount = single_record["cash_amount"]
                        single_card_amount = single_record["card_amount"]
                        single_due_amount = single_record["due_amount"]
                        single_total = single_record["total"]
                        is_same_invoice_exist = Invoice.objects.filter(
                            member__member_ID=single_member_ID,
                            balance_due=single_due_amount,
                            paid_amount=single_card_amount+single_cash_amount,
                            total_amount=single_total,
                            excel_upload_date=lng_date,
                            invoice_type__name="lounge"
                        ).exists()
                        if is_same_invoice_exist:
                            return Response({
                                "code": 400,
                                "status": "failed",
                                "message": "This file was previously uploaded with same data.",
                                "errors": {
                                    "excel_file": ["This file was uploaded previously with same data. If you want to reupload it make sure you have confirm_reupload  attribute set to true."]
                                }
                            }, status=400)
                with transaction.atomic():
                    invoice_type, _ = InvoiceType.objects.get_or_create(
                        name="lounge")
                    cash_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="cash")
                    card_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="card")
                    both_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="both")
                    sale_type, _ = SaleType.objects.get_or_create(
                        name="lounge")
                    full_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                        name="full")
                    partial_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                        name="partial")
                    uploaded_member_data = []
                    for record in data:
                        paid_amount = record["cash_amount"] + \
                            record["card_amount"]
                        total_amount = record["total"]
                        due_amount = record["due_amount"]
                        payment_method = None
                        start_date = lng_date
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
                                member_ID=record["member_ID"])
                        except Member.DoesNotExist:
                            uploaded_member_data.append({
                                "member": record["member_ID"],
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
                            excel_upload_date=lng_date
                        )
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
                        sale_obj = Sale.objects.create(sale_number=generate_unique_sale_number(),
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
                            "status": "success",
                            "reason": "Successfully uploaded"
                        })
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="View",
                        severity_level="info",
                        description="User uploaded an excel file",
                    )
                    return Response({
                        "code": 201,
                        "status": "success",
                        "message": "Data uploaded successfully",
                        "data": uploaded_member_data
                    }, status=status.HTTP_201_CREATED)
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Excel file uploaded successfully",
                    "totals": totals
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="View",
                    severity_level="info",
                    description="User tried to upload an excel file and faced error",
                )
                # return error response
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
                verb="View",
                severity_level="info",
                description="User tried to upload an excel file and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OthersUploadExcelView(APIView):
    permission_classes = [IsAuthenticated, MemberFinancialManagementPermission]

    def post(self, request):
        try:
            serializer = serializers.OthersUploadExcelSerializer(
                data=request.data)
            if serializer.is_valid():
                excel_file = serializer.validated_data["excel_file"]
                uploaded_file = excel_file
                try:
                    file_data_cl = None
                    if uploaded_file.name.endswith('.xlsx'):
                        file_data_cl = pd.read_excel(
                            uploaded_file, engine='openpyxl', dtype=str)
                    elif uploaded_file.name.endswith('.xls'):
                        file_data_cl = pd.read_excel(
                            uploaded_file, engine='xlrd', dtype=str)
                        # Extract and format the date range
                    pick_date = file_data_cl.iat[1, 0]
                    if isinstance(pick_date, str):
                        date_data = pick_date.strip().split(": ")[1]
                        lng_date = datetime.strptime(
                            date_data, "%d.%m.%y").strftime("%Y-%m-%d")

                        sales_date = datetime.strptime(
                            date_data, "%d.%m.%y").date()
                    else:
                        return Response({
                            "code": 400,
                            "status": "failed",
                            "message": "Invalid date format",
                            "errors": {
                                "pick_date": [f"Error: Expected a string, but got {type(pick_date)}. Value: {pick_date}"]
                            }
                        })
                    if file_data_cl is not None:
                        file_data_cl = file_data_cl.dropna(how='all')

                        # Select relevant columns and rename them
                        file_data_cl = file_data_cl[['Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3',
                                                    'Unnamed: 4', 'Unnamed: 5']]
                        file_data_cl.columns = [
                            'member_ID', 'cash_amount', 'card_amount', 'due_amount', 'total']
                        file_data_cl = file_data_cl.iloc[3:-
                                                         1].reset_index(drop=True)
                        # Convert numeric columns
                        numeric_columns = ['cash_amount',
                                           'card_amount', 'due_amount', 'total']
                        file_data_cl[numeric_columns] = file_data_cl[numeric_columns].apply(
                            pd.to_numeric, errors='coerce').fillna(0)
                        # Calculate totals
                        totals = {col: int(file_data_cl[col].sum())
                                  for col in numeric_columns}
                        totals['cash_amount'] = int(totals['cash_amount'])
                        totals['card_amount'] = int(totals['card_amount'])
                        totals['due_amount'] = int(totals['due_amount'])
                        totals['total'] = int(totals['total'])
                except Exception as e:
                    return Response({
                        "code": 400,
                        "status": "failed",
                        "message": "Invalid excel file",
                        "errors": {
                            "excel_file": ["There was an error while reading the excel. Please check if you have uploaded the correct file."]
                        }
                    }, status=400)
                # Process the data as needed
                data = file_data_cl.to_dict(orient='records')
                income_particular = serializer.validated_data["income_particular"]
                received_from = serializer.validated_data["received_from"]
                confirm_reupload = serializer.validated_data["confirm_reupload"]
                if not confirm_reupload:
                    if len(data) >= 1:
                        single_record = data[0]
                        single_member_ID = single_record["member_ID"]
                        single_cash_amount = single_record["cash_amount"]
                        single_card_amount = single_record["card_amount"]
                        single_due_amount = single_record["due_amount"]
                        single_total = single_record["total"]
                        is_same_invoice_exist = Invoice.objects.filter(
                            member__member_ID=single_member_ID,
                            balance_due=single_due_amount,
                            paid_amount=single_card_amount+single_cash_amount,
                            total_amount=single_total,
                            excel_upload_date=lng_date,
                            invoice_type__name="others"
                        ).exists()
                        if is_same_invoice_exist:
                            return Response({
                                "code": 400,
                                "status": "failed",
                                "message": "This file was previously uploaded with same data.",
                                "errors": {
                                    "excel_file": ["This file was uploaded previously with same data. If you want to reupload it make sure you have confirm_reupload  attribute set to true."]
                                }
                            }, status=400)
                with transaction.atomic():
                    invoice_type, _ = InvoiceType.objects.get_or_create(
                        name="others")
                    cash_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="cash")
                    card_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="card")
                    both_payment_method, _ = PaymentMethod.objects.get_or_create(
                        name="both")
                    sale_type, _ = SaleType.objects.get_or_create(
                        name="others")
                    full_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                        name="full")
                    partial_income_receiving_type, _ = IncomeReceivingType.objects.get_or_create(
                        name="partial")
                    uploaded_member_data = []
                    for record in data:
                        paid_amount = record["cash_amount"] + \
                            record["card_amount"]
                        total_amount = record["total"]
                        due_amount = record["due_amount"]
                        payment_method = None
                        start_date = lng_date
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
                                member_ID=record["member_ID"])
                        except Member.DoesNotExist:
                            uploaded_member_data.append({
                                "member": record["member_ID"],
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
                            excel_upload_date=lng_date,
                            invoice_type=invoice_type,
                            generated_by=request.user,
                            member=member)
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
                        sale_obj = Sale.objects.create(sale_number=generate_unique_sale_number(),
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
                            "status": "success",
                            "reason": "Successfully uploaded"
                        })
                    log_activity_task.delay_on_commit(
                        request_data_activity_log(request),
                        verb="View",
                        severity_level="info",
                        description="User uploaded an excel file",
                    )
                    return Response({
                        "code": 201,
                        "status": "success",
                        "message": "Data uploaded successfully",
                        "data": uploaded_member_data
                    }, status=status.HTTP_201_CREATED)
                return Response({
                    "code": 200,
                    "status": "success",
                    "message": "Excel file uploaded successfully",
                    "totals": totals
                }, status=status.HTTP_200_OK)
            else:
                # activity log
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="View",
                    severity_level="info",
                    description="User tried to upload an excel file and faced error",
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
                verb="View",
                severity_level="info",
                description="User tried to upload an excel file and faced error",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
