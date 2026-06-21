from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
import logging

from member_financial_management.models import Invoice
from .services.sslcommerz_service import (
    initiate_session, validate_ipn, SSLCommerzError,
)

logger = logging.getLogger("myapp")


def _envelope(code, status_str, message, **extra):
    body = {"code": code, "status": status_str, "message": message}
    body.update(extra)
    return body


class SSLCommerzInitiateView(APIView):
    """Start a hosted-checkout session for an existing invoice."""
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(_envelope(404, "failed", "Invoice not found"),
                            status=status.HTTP_404_NOT_FOUND)
        if invoice.status == "paid":
            return Response(_envelope(400, "failed", "Invoice already paid"),
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = invoice.balance_due or invoice.total_amount
            data = initiate_session(
                invoice=invoice, amount=amount,
                customer_name=getattr(invoice.member, "first_name", "Member") or "Member",
            )
            return Response(_envelope(200, "success", "Session created", data={
                "gateway_url": data.get("GatewayPageURL"),
                "sessionkey": data.get("sessionkey"),
                "tran_id": invoice.invoice_number,
            }))
        except SSLCommerzError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "Something went wrong",
                            errors={"server_error": [str(e)]}),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SSLCommerzIPNView(APIView):
    """
    Server-to-server callback from SSLCommerz. Must be public (no auth) but it
    re-validates every payment with the gateway before trusting it.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            invoice = validate_ipn(post_data=request.data)
            if invoice is None:
                return Response(_envelope(200, "success", "IPN received, no action"))
            return Response(_envelope(200, "success", "Payment validated",
                            data={"invoice": invoice.invoice_number,
                                  "status": invoice.status}))
        except SSLCommerzError as e:
            return Response(_envelope(400, "failed", str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(str(e))
            return Response(_envelope(500, "failed", "IPN processing error"),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
