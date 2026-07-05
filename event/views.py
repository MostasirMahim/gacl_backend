
from .utils.permission_classes import EventManagementPermission
from django.utils.http import urlencode
from django.core.cache import cache
from core.utils.pagination import CustomPageNumberPagination
import pdb
from django.shortcuts import render
from rest_framework.views import APIView
from event import serializers
from rest_framework.response import Response
from rest_framework import status
from .models import Venue, Event, EventTicket, EventMedia, EventFee
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from activity_log.tasks import log_activity_task
from activity_log.utils.functions import request_data_activity_log
from member_financial_management.utils.functions import generate_unique_invoice_number
from member.models import Member
from django.db import transaction
from member_financial_management.serializers import InvoiceSerializer
from member_financial_management.models import Invoice, InvoiceItem, InvoiceType
from promo_code_app.models import PromoCode, AppliedPromoCode
from datetime import date
from django.utils.decorators import method_decorator
from member_financial_management.utils.permission_classes import MemberFinancialManagementPermission
import logging
logger = logging.getLogger("myapp")
from .tasks import delete_events_cache, delete_event_venues_cache
# Create your views here.


class EventVenueView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        
        try:
            data = request.data
            serializer = serializers.EventVenueSerializer(data=data)
            if serializer.is_valid():

                venue_instance = serializer.save()
            
                street_address = serializer.validated_data["street_address"]
                city = serializer.validated_data["city"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Venue created successfully",
                    severity_level="info",
                    description="Venue created successfully for register a event",
                )
                # Delete the cache for event venues
                delete_event_venues_cache.delay()
                return Response({
                    "code": 201,
                    "message": "Venue created successfully",
                    "status": "success",
                    "data": {
                        "venue_id": venue_instance.id,
                        "street_address": street_address,
                        "city": city

                    }
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Venue creation failed",
                    severity_level="error",
                    description="user tried to create a new venue but made an invalid request",
                )
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Venue creation failed",
                severity_level="error",
                description="user tried to create a new venue but made an invalid request",
            )
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
    
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"event_venues::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)
            paginator = CustomPageNumberPagination()
            venues = Venue.objects.filter(is_active=True).order_by('id')
            all_venues = paginator.paginate_queryset(
                venues, request, view=self)
            serializer = serializers.EventVenueViewSerializer(
                all_venues, many=True)
            data = serializer.data

            # Log the activity
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Retrieve all venues",
                severity_level="info",
                description="User retrieved all venues successfully",
            )

            final_response = paginator.get_paginated_response({
                "code": 200,
                "message": "Venues retrieved successfully",
                "status": "success",
                "data": data
            })
            # Cache the response
            cache.set(cache_key, final_response.data, timeout=60*30)
            return final_response

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Venues retrieve failed",
                severity_level="error",
                description="Error occurred while retrieving all venues",
            )

            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventView(APIView):
    def get_permissions(self):
        if self.request.method in ["POST", "GET"]:
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
       
        try:
            data = request.data
            serializer = serializers.EventSerializer(data=data)
            if serializer.is_valid():
                event_instance = serializer.save()
                event_title = serializer.validated_data["title"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event created successfully",
                    severity_level="info",
                    description="Event created successfully for register a event",)
                # delete the cache for events
                delete_events_cache.delay()
                return Response({
                    "code": 201,
                    "message": "Event created successfully",
                    "status": "success",
                    "data": {
                        "event_id": event_instance.id,
                        "event_title": event_title,

                    }
                }, status=status.HTTP_201_CREATED)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event creation failed",
                    severity_level="error",
                    description="user tried to create a new event but made an invalid request",)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event creation failed",
                severity_level="error",
                description="user tried to create a new event but made an invalid request",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
       
        try:
            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"events::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)
            paginator = CustomPageNumberPagination()
            events = (
                Event.objects.filter(is_active=True)
                .select_related('venue', 'organizer')
                .prefetch_related('event_media')
                .order_by('id')
            )
            all_events = paginator.paginate_queryset(
                events, request, view=self)
            serializer = serializers.EventViewSerializer(all_events, many=True)
            data = serializer.data

            # Log the activity
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Retrieve all events",
                severity_level="info",
                description="User retrieved all events successfully",)
            final_response = paginator.get_paginated_response({
                "code": 200,
                "message": "Events retrieved successfully",
                "status": "success",
                "data": data
            })
            cache.set(cache_key, final_response.data, timeout=60*10)#cache for 10 minutes
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Events retrieve failed",
                severity_level="error",
                description="Error occurred while retrieving all events",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def get(self, request, event_id):
        
        try:
            # cache_key = f"event_details::{event_id}"
            # cached_response = cache.get(cache_key)
            # if cached_response:
            #     return Response(cached_response, status=200)
            event = Event.objects.select_related("organizer", "venue")\
                                 .prefetch_related("event_media")\
                                 .get(pk=event_id)
            serializer = serializers.EventViewSerializer(event)
            log_activity_task.delay_on_commit(

                request_data_activity_log(request),
                verb="Retrieve event details",
                severity_level="info",
                description="User retrieved event details successfully",)
            final_response = Response({
                "code": 200,
                "message": "Event details retrieved successfully",
                "status": "success",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            # Cache the response
            # cache.set(cache_key, final_response.data, timeout=60 * 30)
            return final_response
        except Event.DoesNotExist:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event details retrieve failed",
                severity_level="error",
                description="Error occurred while retrieving specific event details",)
            return Response({
                "code": status.HTTP_404_NOT_FOUND,
                "message": "Event not found",
                "status": "failed",
                "errors": {
                    "event": ["Event not found"]
                }})

        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event details retrieve failed",
                severity_level="error",
                description="Error occurred while retrieving event details",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            })


class EventTicketView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        
        try:
            data = request.data
            serializer = serializers.EventTicketSerializer(data=data)
            if serializer.is_valid():
                ticket_instance = serializer.save()
                # delete the cache for event tickets
                cache.delete_pattern("event_tickets::*")
                ticket_name = serializer.validated_data["ticket_name"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event ticket created successfully",
                    severity_level="info",
                    description="Event ticket created successfully for register a event",)
                return Response({
                    "code": 201,
                    "message": "Event ticket created successfully",
                    "status": "success",
                    "data": {
                        "ticket_id": ticket_instance.id,
                        "ticket_name": ticket_name
                    }})
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event ticket creation failed",
                    severity_level="error",
                    description="user tried to create a new event ticket but made an invalid request",)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event ticket creation failed",
                severity_level="error",
                description="user tried to create a new event ticket but made an invalid request",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """
        Retrieves a list of all event tickets and logs an activity.
        Returns:
            Response: The response containing the list of event tickets.
        """
        try:

            query_items = sorted(request.query_params.items())
            query_string = urlencode(query_items) if query_items else "default"
            cache_key = f"event_tickets::{query_string}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=200)
            event_ticket = EventTicket.objects.filter(is_active=True).select_related("event").order_by('id')
            event_id = request.query_params.get("event")
            if event_id:
                event_ticket = event_ticket.filter(event_id=event_id)
            paginator = CustomPageNumberPagination()
            # Implement pagination
            all_event_ticket = paginator.paginate_queryset(
                event_ticket, request, view=self)
            serializer = serializers.EventTicketViewSerializer(
                all_event_ticket, many=True)
            data = serializer.data

            # Log the activity
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Retrieve all event tickets",
                severity_level="info",
                description="User retrieved all event tickets successfully",)
            final_response = paginator.get_paginated_response({
                "code": 200,
                "message": "Event tickets retrieved successfully",
                "status": "success",
                "data": data
            })
            cache.set(cache_key, final_response.data, timeout=60 * 30)
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event tickets retrieve failed",
                severity_level="error",
                description="Error occurred while retrieving all event tickets",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventMediaView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
       
        try:
            data = request.data
            serializer = serializers.EventMediaSerializer(data=data)
            if serializer.is_valid():
                media_instance = serializer.save()
                event_instance = serializer.validated_data["event"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event media created successfully",
                    severity_level="info",
                    description="Event media created successfully for register a event"
                )
                return Response({
                    "code": 201,
                    "message": "Event media created successfully",
                    "status": "success",
                    "data": {
                        "image_id": media_instance.id,
                        "event_id": event_instance.id
                    }
                })
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event media creation failed",
                    severity_level="error",
                    description="user tried to create a new event media but made an invalid request",)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event media creation failed",
                severity_level="error",
                description="user tried to create a new event media but made an invalid request",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventFeeView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        
        try:
            data = request.data
            serializer = serializers.EventFeeSerializer(data=data)
            if serializer.is_valid():
                fee_instance = serializer.save()
                # delete the cache for event fees
                # cache.delete_pattern("event_fees::*")
                event_fee = serializer.validated_data["fee"]
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event fee created successfully",
                    severity_level="info",
                    description="Event fee created successfully for register a event",)
                return Response({
                    "code": 201,
                    "message": "Event fee created successfully",
                    "status": "success",
                    "data": {
                        "fee_id": fee_instance.id,
                        "event_fee": event_fee,

                    }
                })
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Event fee creation failed",
                    severity_level="error",
                    description="user tried to create a new event fee but made an invalid request",)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event fee creation failed",
                severity_level="error",
                description="user tried to create a new event fee but made an invalid request",)
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        
        try:
            # query_items = sorted(request.query_params.items())
            # query_string = urlencode(query_items) if query_items else "default"
            # cache_key = f"event_fees::{query_string}"
            # cached_response = cache.get(cache_key)
            # if cached_response:
            #     return Response(cached_response, status=200)
            event_fees = EventFee.objects.filter(is_active=True).order_by('id')
            # Implement pagination
            paginator = CustomPageNumberPagination()
            all_event_fees = paginator.paginate_queryset(
                event_fees, request, view=self)
            serializer = serializers.EventFeeViewSerializer(
                all_event_fees, many=True)
            data = serializer.data
            # Log the activity
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Retrieve all event fees",
                severity_level="info",
                description="User retrieved all event fees successfully",)
            final_response = paginator.get_paginated_response({
                "code": 200,
                "message": "Event fees retrieved successfully",
                "status": "success",
                "data": data
            })
            # Cache the data
            # cache.set(cache_key, final_response.data, timeout=60 * 30)
            return final_response
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event fees retrieve failed",
                severity_level="error",
                description="Error occurred while retrieving all event fees")
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventTicketDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        else:
            return [IsAuthenticated()]

    def get(self, request, ticket_id):
        try:
            # cache_key = f"event_ticket_details::{ticket_id}"
            # cached_response = cache.get(cache_key)
            # if cached_response:
            #     return Response(cached_response, status=200)
            event_ticket = EventTicket.objects.select_related(
                'event').get(pk=ticket_id)
            serializer = serializers.EventTicketViewSerializer(event_ticket)
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="View event ticket details",
                severity_level="info",
                description="User viewed event ticket details",
            )
            final_response = Response({
                "code": 200,
                "status": "success",
                "message": "Event ticket details",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            # Cache the response
            # cache.set(cache_key, final_response.data, timeout=60 * 30)
            return final_response
        except EventTicket.DoesNotExist:
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event ticket details retrieve failed",
                severity_level="info",
                description="User tried to view event ticket details but event ticket not found",
            )
            return Response({
                "code": 404,
                "status": "failed",
                "message": "Event ticket not found",
                "errors": {
                    "event_ticket": ["Event ticket not found"]
                }
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Event ticket details retrieve failed",
                severity_level="info",
                description="Error occurred while retrieving event ticket details",
            )
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Something went wrong",
                "errors": {
                    "server_error": [str(e)]
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventTicketBuyView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), MemberFinancialManagementPermission()]
        else:
            return [IsAuthenticated()]

    def post(self, request):
        
        try:
            data = request.data
            serializer = serializers.EventTicketBuySerializer(data=data)
            if serializer.is_valid():

                member = serializer.validated_data["member_ID"]
                member = Member.objects.get(member_ID=member)
                event_ticket = serializer.validated_data["event_ticket"]
                promo_code = serializer.validated_data["promo_code"]
                discount = 0
                total_amount = event_ticket.price
                if promo_code is not None:
                    if promo_code.percentage is not None:
                        percentage = promo_code.percentage
                        discount = (percentage/100) * total_amount
                        total_amount = total_amount - discount
                    else:
                        discount = promo_code.amount
                        if discount <= total_amount:
                            total_amount = total_amount - discount
                        else:
                            discount = total_amount
                            total_amount = 0
                    promo_code.remaining_limit -= 1
                    promo_code.save(update_fields=["remaining_limit"])
                else:
                    promo_code = ""
                invoice_type, _ = InvoiceType.objects.get_or_create(
                    name="Event")

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
                        event=event_ticket.event,
                        discount=discount,
                        promo_code=promo_code,
                    )
                    if promo_code != "":
                        AppliedPromoCode.objects.create(
                            discounted_amount=discount, promo_code=promo_code, used_by=member)
                    invoice_item = InvoiceItem.objects.create(
                        invoice=invoice
                    )
                    invoice_item.event_tickets.set([event_ticket.id])

                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Invoice created successfully",
                    severity_level="info",
                    description="user generated an invoice successfully",)
                # delete the cache for invoices
                return Response({
                    "code": 200,
                    "message": "Invoice created successfully",
                    "status": "success",
                    "data": InvoiceSerializer(invoice).data
                }, status=status.HTTP_200_OK)
            else:
                log_activity_task.delay_on_commit(
                    request_data_activity_log(request),
                    verb="Invoice creation failed",
                    severity_level="error",
                    description="user tried to generate an invoice but made an invalid request",)
                return Response({
                    "code": 400,
                    "status": "failed",
                    "message": "Invalid request",
                    "errors": serializer.errors,
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            log_activity_task.delay_on_commit(
                request_data_activity_log(request),
                verb="Invoice creation failed",
                severity_level="error",
                description="user tried to generate an invoice but made an invalid request",)
            return Response({

                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                'errors': {
                    'server_error': [str(e)]
                }}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== EVENT EXPENSE / FOOD TRACKING VIEWS =====
from event.models import EventExpenseCategory, EventExpense, EventFoodItem


class EventExpenseView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = EventExpense.objects.filter(is_active=True)
        event_id = request.query_params.get("event_id")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return Response({
            "code": 200, "status": "success", "message": "Event expenses",
            "data": serializers.EventExpenseSerializer(qs, many=True).data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        s = serializers.EventExpenseSerializer(data=request.data)
        if s.is_valid():
            expense = s.save()
            # mirror into the central expense ledger
            try:
                from finance_core.services.ledger_service import record_expense
                record_expense(
                    source_module="event", category_name="Event Cost",
                    amount=expense.amount,
                    description=f"{expense.title} ({expense.event.title})",
                    reference_type="event_expense", reference_id=expense.id,
                    created_by=request.user)
            except Exception as exc:
                logger.warning("Could not record event expense centrally: %s", exc)
            return Response({
                "code": 201, "status": "success", "message": "Expense recorded",
                "data": serializers.EventExpenseSerializer(expense).data,
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": 400, "status": "failed", "message": "Bad request",
            "errors": s.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class EventExpenseCategoryView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = EventExpenseCategory.objects.filter(is_active=True)
        return Response({
            "code": 200, "status": "success", "message": "Categories",
            "data": serializers.EventExpenseCategorySerializer(qs, many=True).data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        s = serializers.EventExpenseCategorySerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response({
                "code": 201, "status": "success", "message": "Category created",
                "data": s.data,
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": 400, "status": "failed", "message": "Bad request",
            "errors": s.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class EventFoodItemView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), EventManagementPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = EventFoodItem.objects.filter(is_active=True)
        event_id = request.query_params.get("event_id")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return Response({
            "code": 200, "status": "success", "message": "Event food items",
            "data": serializers.EventFoodItemSerializer(qs, many=True).data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        s = serializers.EventFoodItemSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response({
                "code": 201, "status": "success", "message": "Food item added",
                "data": s.data,
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": 400, "status": "failed", "message": "Bad request",
            "errors": s.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class EventProfitabilityView(APIView):
    """Ticket income vs. expenses for an event."""
    permission_classes = [IsAuthenticated, EventManagementPermission]

    def get(self, request, event_id):
        from django.db.models import Sum
        from decimal import Decimal
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response({"code": 404, "status": "failed",
                             "message": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
        expense_total = (EventExpense.objects.filter(event=event, is_active=True)
                         .aggregate(t=Sum("amount"))["t"] or Decimal("0"))
        # income: invoices generated for this event that were paid
        income_total = (Invoice.objects.filter(event=event, is_active=True)
                        .aggregate(t=Sum("paid_amount"))["t"] or Decimal("0"))
        return Response({
            "code": 200, "status": "success", "message": "Event profitability",
            "data": {
                "event_id": event.id, "title": event.title,
                "ticket_income": income_total, "total_expense": expense_total,
                "net": income_total - expense_total,
            },
        }, status=status.HTTP_200_OK)


class CountryChoicesView(APIView):
    """Bug 7.2: serve country choices for the venue country dropdown."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import COUNTRY_CHOICES
        # Put Bangladesh first as the club is BD-based, then the rest.
        data = [{"code": c, "name": n} for c, n in COUNTRY_CHOICES]
        data.sort(key=lambda x: (x["code"] != "BD", x["name"]))
        return Response({"code": 200, "status": "success",
                         "message": "Country choices", "data": data})
