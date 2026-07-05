"""
Member self-service portal endpoints.

All endpoints here are for a logged-in *member* (Member.user) and only ever
expose that member's own data. Staff/admin can also call them for their own
linked member if any, but the intended audience is club members using the
portal to place/track their own orders, reservations and bills.
"""
from decimal import Decimal

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q

from member.models import Member
from member.utils.scoping import get_member_for_user, is_member_user
from event.models import Event, EventTicket
from event.serializers import EventViewSerializer
from member_financial_management.models import Invoice, InvoiceItem, InvoiceType
from member_financial_management.utils.functions import generate_unique_invoice_number
from promo_code_app.models import PromoCode, AppliedPromoCode
from django.db import transaction
from datetime import date


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


def _require_member(request):
    """Return (member, error_response). error_response is None on success."""
    member = get_member_for_user(request.user)
    if member is None:
        return None, Response(
            _envelope(403, "failed",
                      "This endpoint is for club members only."),
            status=status.HTTP_403_FORBIDDEN)
    return member, None


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member, err = _require_member(request)
        if err:
            return err
        from member.models import Member
        from member import serializers
        try:
            # Re-fetch with prefetch_related for rich structure like MemberView
            member_obj = Member.objects.select_related(
                'marital_status', 'membership_status', 'institute_name',
                'membership_type', 'gender'
            ).prefetch_related(
                "contact_numbers", "emails", "addresses", "spouse", "descendants",
                "professions", "emergency_contacts", "companions", "credentials",
                "certificates", "special_days"
            ).get(member_ID=member.member_ID)

            data = {
                'member_info': serializers.MemberSerializerForViewSingleMember(member_obj).data,
                'contact_info': serializers.MemberContactNumberViewSerializer(member_obj.contact_numbers, many=True).data,
                'email_address': serializers.MemberEmailAddressViewSerializer(member_obj.emails, many=True).data,
                'address': serializers.MemberAddressViewSerializer(member_obj.addresses, many=True).data,
                'job': serializers.MemberJobViewSerializer(member_obj.professions, many=True).data,
                'spouse': serializers.MemberSpouseViewSerializer(member_obj.spouse, many=True).data,
                'descendant': serializers.MemberDescendantsViewSerializer(member_obj.descendants, many=True).data,
                'emergency_contact': serializers.MemberEmergencyContactViewSerializer(member_obj.emergency_contacts, many=True).data,
                'certificate': serializers.MemberCertificateViewSerializer(member_obj.certificates, many=True).data,
                'companion': serializers.MemberCompanionViewSerializer(member_obj.companions, many=True).data,
                'document': serializers.MemberDocumentsViewSerializer(member_obj.credentials, many=True).data,
                'special_days': serializers.MemberSpecialDaysViewSerializer(member_obj.special_days, many=True).data,
            }
        except Exception as e:
            # fall back to a minimal profile if the rich serializer needs extras
            data = {
                "id": member.id, "member_ID": member.member_ID,
                "first_name": member.first_name, "last_name": member.last_name,
                "blood_group": member.blood_group,
            }
        return Response(_envelope(200, "success", "My profile", data=data))


class MyDashboardView(APIView):
    """Member-only dashboard: counts + spend for *this* member, nothing global."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member, err = _require_member(request)
        if err:
            return err

        from restaurant.models import RestaurantOrder
        from outlet.models import OutletOrder
        from reservation.models import Reservation
        from member_financial_management.models import Invoice

        r_orders = RestaurantOrder.objects.filter(member=member, is_active=True)
        o_orders = OutletOrder.objects.filter(member=member, is_active=True)
        reservations = Reservation.objects.filter(member=member, is_active=True)
        invoices = Invoice.active_objects.filter(member=member)

        outstanding = invoices.filter(is_full_paid=False).aggregate(
            t=Sum("balance_due"))["t"] or Decimal("0")
        total_spend = invoices.aggregate(t=Sum("total_amount"))["t"] or Decimal("0")

        data = {
            "member_ID": member.member_ID,
            "member_name": f"{member.first_name} {member.last_name}".strip(),
            "restaurant_orders": r_orders.count(),
            "outlet_orders": o_orders.count(),
            "active_orders": (
                r_orders.exclude(status__in=["billed", "cancelled"]).count() +
                o_orders.exclude(status__in=["billed", "cancelled"]).count()),
            "reservations": reservations.count(),
            "upcoming_reservations": reservations.filter(
                status__in=["pending_payment", "confirmed"]).count(),
            "invoices": invoices.count(),
            "unpaid_invoices": invoices.filter(is_full_paid=False).count(),
            "outstanding_balance": str(outstanding),
            "lifetime_spend": str(total_spend),
        }
        return Response(_envelope(200, "success", "My dashboard", data=data))


class MyOrdersView(APIView):
    """Combined restaurant + outlet orders for the logged-in member."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member, err = _require_member(request)
        if err:
            return err
        from restaurant.models import RestaurantOrder
        from outlet.models import OutletOrder
        from restaurant import serializers as r_ser
        from outlet import serializers as o_ser

        kind = request.query_params.get("kind")  # 'restaurant' | 'outlet' | None
        result = []
        if kind in (None, "restaurant"):
            r = RestaurantOrder.objects.prefetch_related("items").filter(
                member=member, is_active=True).order_by("-created_at")
            for o in r:
                d = r_ser.RestaurantOrderViewSerializer(o).data
                d["order_kind"] = "restaurant"
                result.append(d)
        if kind in (None, "outlet"):
            o = OutletOrder.objects.prefetch_related("items").filter(
                member=member, is_active=True).order_by("-created_at")
            for ord_ in o:
                d = o_ser.OutletOrderViewSerializer(ord_).data
                d["order_kind"] = "outlet"
                result.append(d)
        # newest first across both
        result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return Response(_envelope(200, "success", "My orders", data=result))


class MyReservationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member, err = _require_member(request)
        if err:
            return err
        from reservation.models import Reservation
        from reservation import serializers as ser
        qs = Reservation.objects.select_related("resource").filter(
            member=member, is_active=True).order_by("-created_at")
        data = ser.ReservationViewSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "My reservations", data=data))


class MyInvoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member, err = _require_member(request)
        if err:
            return err
        from member_financial_management.models import Invoice
        from member_financial_management import serializers as ser
        qs = Invoice.active_objects.select_related(
            "invoice_type", "member").filter(member=member).order_by("-id")
        unpaid = request.query_params.get("unpaid")
        if unpaid == "true":
            qs = qs.filter(is_full_paid=False)
        try:
            data = ser.InvoiceForViewSerializer(qs, many=True).data
        except Exception:
            data = [{
                "id": inv.id, "total_amount": str(inv.total_amount),
                "balance_due": str(inv.balance_due),
                "is_full_paid": inv.is_full_paid, "status": inv.status,
            } for inv in qs]
        return Response(_envelope(200, "success", "My invoices", data=data))


class MyInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        member, err = _require_member(request)
        if err:
            return err
        from member_financial_management.models import Invoice
        from member_financial_management import serializers as ser
        try:
            inv = Invoice.active_objects.select_related("invoice_type", "member").prefetch_related("invoice_items").get(id=invoice_id, member=member)
        except Invoice.DoesNotExist:
            return Response(_envelope(404, "failed", "Invoice not found"), status=status.HTTP_404_NOT_FOUND)
        
        data = ser.InvoiceForViewSerializer(inv).data
        return Response(_envelope(200, "success", "My invoice detail", data=data))


class PayMyInvoiceView(APIView):
    """
    Member pays one of their own invoices. Two modes:
      - 'online'  : initiate an SSLCommerz session (returns gateway URL)
      - 'due'     : charge to the member's account/due (admin settles later)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        member, err = _require_member(request)
        if err:
            return err
        from member_financial_management.models import Invoice
        try:
            invoice = Invoice.active_objects.get(id=invoice_id, member=member)
        except Invoice.DoesNotExist:
            return Response(_envelope(404, "failed",
                            "Invoice not found or not yours"),
                            status=status.HTTP_404_NOT_FOUND)
        if invoice.is_full_paid:
            return Response(_envelope(400, "failed", "Invoice already paid"),
                            status=status.HTTP_400_BAD_REQUEST)

        mode = (request.data.get("mode") or "online").lower()

        if mode == "due":
            # mark as charged-to-account; admin settles later. We flag the
            # invoice status without touching the ledger totals so finance
            # reports stay accurate until real settlement.
            invoice.status = "due"
            invoice.save(update_fields=["status", "updated_at"])
            return Response(_envelope(200, "success",
                            "Charged to your club account. "
                            "The club will settle this against your dues."))

        # online: try to initiate an SSLCommerz session if available
        try:
            from finance_core.services.sslcommerz_service import initiate_session
            session = initiate_session(
                invoice=invoice,
                amount=invoice.balance_due,
                customer_name=f"{member.first_name} {member.last_name}" if member else "Member",
            )
            return Response(_envelope(200, "success",
                            "Payment session initiated",
                            data={"gateway_url": session.get("GatewayPageURL")
                                  or session.get("redirect_url"),
                                  "raw": session}))
        except Exception:
            # graceful fallback: return the intent so the frontend can render
            # its own SSLCommerz redirect using existing config.
            return Response(_envelope(200, "success",
                            "Proceed to online payment",
                            data={"invoice_id": invoice.id,
                                  "amount": str(invoice.balance_due),
                                  "mode": "online",
                                  "gateway_url": None}))


class AvailableEventsView(APIView):
    """
    Member portal: View all active events
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member, err = _require_member(request)
        if err:
            return err
        qs = Event.objects.filter(is_active=True).select_related("venue", "organizer").prefetch_related("event_media").order_by("-id")
        data = EventViewSerializer(qs, many=True).data
        return Response(_envelope(200, "success", "Available events", data=data))


class PortalEventTicketBuyView(APIView):
    """
    Member portal: Buy an event ticket for the logged-in member.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        member, err = _require_member(request)
        if err:
            return err

        ticket_id = request.data.get("ticket_id")
        promo_code_str = request.data.get("promo_code")

        try:
            event_ticket = EventTicket.objects.get(id=ticket_id, status="available")
        except EventTicket.DoesNotExist:
            return Response(_envelope(404, "failed", "Ticket not found or unavailable"), status=status.HTTP_404_NOT_FOUND)

        discount = 0
        total_amount = event_ticket.price
        promo_code = None

        if promo_code_str:
            try:
                promo_code = PromoCode.objects.get(promo_code=promo_code_str)
                if not promo_code.is_promo_code_valid():
                    return Response(_envelope(400, "failed", "Promo code expired or invalid"), status=status.HTTP_400_BAD_REQUEST)
                if not promo_code.category.filter(name__iexact="event").exists():
                    return Response(_envelope(400, "failed", "Not an event promo code"), status=status.HTTP_400_BAD_REQUEST)
                
                if promo_code.percentage is not None:
                    discount = (promo_code.percentage / 100) * total_amount
                    total_amount = total_amount - discount
                else:
                    discount = promo_code.amount
                    if discount <= total_amount:
                        total_amount = total_amount - discount
                    else:
                        discount = total_amount
                        total_amount = 0
            except PromoCode.DoesNotExist:
                return Response(_envelope(404, "failed", "Promo code not found"), status=status.HTTP_404_NOT_FOUND)

        invoice_type, _ = InvoiceType.objects.get_or_create(name="Event")

        try:
            with transaction.atomic():
                invoice = Invoice.objects.create(
                    currency="BDT",
                    invoice_number=generate_unique_invoice_number(),
                    balance_due=total_amount,
                    paid_amount=0,
                    issue_date=date.today(),
                    total_amount=total_amount,
                    is_full_paid=(total_amount <= 0),
                    status="unpaid" if total_amount > 0 else "paid",
                    invoice_type=invoice_type,
                    generated_by=request.user,
                    member=member,
                    event=event_ticket.event,
                    discount=discount,
                    promo_code=promo_code if promo_code else "",
                )
                if promo_code:
                    AppliedPromoCode.objects.create(
                        discounted_amount=discount, promo_code=promo_code, used_by=member)
                    promo_code.remaining_limit -= 1
                    promo_code.save(update_fields=["remaining_limit"])

                invoice_item = InvoiceItem.objects.create(invoice=invoice)
                invoice_item.event_tickets.set([event_ticket.id])
                
            # Returning the invoice ID so they can go to the pay screen if needed
            return Response(_envelope(200, "success", "Ticket booked successfully", data={"invoice_id": invoice.id, "balance_due": str(invoice.balance_due)}))
            
        except Exception as e:
            return Response(_envelope(500, "failed", str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
