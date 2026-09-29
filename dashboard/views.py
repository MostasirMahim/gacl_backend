from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.db.models import (
    Count, Q, Sum, Avg, F, ExpressionWrapper, DecimalField
)
from django.db.models.functions import TruncMonth, TruncHour, TruncDate
from django.utils import timezone
from django.core.cache import cache

import datetime
import logging

from activity_log.tasks import log_activity_task
from activity_log.utils.functions import request_data_activity_log
from activity_log.models import ActivityLog

from member.models import Member, MembershipType
from restaurant.models import Restaurant, RestaurantOrder, RestaurantItem
from event.models import Event
from account.models import GroupModel, AssignGroupPermission
from product.models import Product
from .overview_builder import _build_overview_section

logger = logging.getLogger("myapp")

User = get_user_model()

# ---------------------------------------------------------------------------
# Permission helper
# Reads the same cache that HasCustomPermission writes, so no extra DB hits
# ---------------------------------------------------------------------------

def _get_user_permissions(user):
    """Return a set of permission name strings for the given user."""
    if getattr(user, "is_superuser", False):
        return {"__superuser__"}  # sentinel: always grants everything

    cache_key = f"user_permissions_{user.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    # Recompute exactly as HasCustomPermission does
    all_user_groups = AssignGroupPermission.objects.filter(
        user=user
    ).prefetch_related("group__permission")
    perms = set()
    for assign_group in all_user_groups:
        for group in assign_group.group.all():
            for perm in group.permission.all():
                perms.add(perm.name)

    if getattr(user, "role", None) == "MEMBER":
        from account.models import GroupModel
        member_group = GroupModel.objects.filter(
            name="club_member"
        ).prefetch_related("permission").first()
        if member_group:
            for perm in member_group.permission.all():
                perms.add(perm.name)

    cache.set(cache_key, list(perms), timeout=60 * 5)
    return perms


def _has(perms_set, *required):
    """Return True if user is superuser OR has ANY of the required perms."""
    if "__superuser__" in perms_set:
        return True
    return any(p in perms_set for p in required)


# ---------------------------------------------------------------------------
# Section builders — each function does ONE focused query block
# ---------------------------------------------------------------------------

def _build_member_section(params):
    """
    Requires: member:view
    Returns member KPIs, 12-month growth trend, membership-type breakdown,
    pending approval queue (top 5), upcoming birthdays (next 7 days).
    """
    today = now().date()

    total = Member.objects.count()
    active = Member.objects.filter(
        membership_status__name__iexact="active"
    ).count()
    pending_status = Member.objects.filter(
        membership_status__name__iexact="pending"
    ).count()
    pending_approval = Member.objects.filter(
        application_status="pending"
    ).count()
    inactive = Member.objects.filter(is_active=False).count()

    # New members this month
    first_of_month = today.replace(day=1)
    new_this_month = Member.objects.filter(
        created_at__date__gte=first_of_month
    ).count()

    # 12-month growth trend
    twelve_months_ago = today - datetime.timedelta(days=365)
    growth_qs = (
        Member.objects.filter(created_at__date__gte=twelve_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    growth_chart = [
        {
            "month": row["month"].strftime("%b %Y"),
            "new_members": row["count"],
        }
        for row in growth_qs
    ]

    # Membership type breakdown (active vs pending per type)
    type_breakdown_qs = (
        Member.objects.values("membership_type__name")
        .annotate(
            active=Count("id", filter=Q(membership_status__name__iexact="active")),
            pending=Count("id", filter=Q(membership_status__name__iexact="pending")),
            total=Count("id"),
        )
        .order_by("membership_type__name")
    )
    type_breakdown = [
        {
            "membership_type": row["membership_type__name"],
            "active": row["active"],
            "pending": row["pending"],
            "total": row["total"],
        }
        for row in type_breakdown_qs
    ]

    # Pending approvals queue (top 5 newest)
    pending_queue = list(
        Member.objects.filter(application_status="pending")
        .order_by("-created_at")
        .values(
            "id",
            "first_name",
            "last_name",
            "member_ID",
            "created_at",
            "membership_type__name",
        )[:5]
    )
    for item in pending_queue:
        item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None

    # Upcoming birthdays (next 7 days) — compare month+day only
    birthday_window = [today + datetime.timedelta(days=i) for i in range(8)]
    month_day_pairs = [(d.month, d.day) for d in birthday_window]
    birthday_q = Q()
    for m, d in month_day_pairs:
        birthday_q |= Q(date_of_birth__month=m, date_of_birth__day=d)
    upcoming_birthdays = list(
        Member.objects.filter(birthday_q, is_active=True)
        .values("id", "first_name", "last_name", "member_ID", "date_of_birth")[:10]
    )
    for b in upcoming_birthdays:
        b["date_of_birth"] = b["date_of_birth"].isoformat() if b["date_of_birth"] else None

    return {
        "kpi": {
            "total_members": total,
            "active_members": active,
            "pending_status_members": pending_status,
            "pending_approval_members": pending_approval,
            "inactive_members": inactive,
            "new_this_month": new_this_month,
        },
        "growth_chart": growth_chart,
        "type_breakdown": type_breakdown,
        "pending_approval_queue": pending_queue,
        "upcoming_birthdays": upcoming_birthdays,
    }


def _build_finance_section():
    """
    Requires: member_financial:view_invoices
    Returns MTD revenue (from Income), outstanding dues,
    invoice status breakdown, top-5 debtors.
    """
    from member_financial_management.models import (
        Invoice, MemberAccount, Income, Transaction, Sale
    )

    today = now().date()
    first_of_month = today.replace(day=1)

    # Invoice KPIs
    invoice_qs = Invoice.objects.all()
    total_invoices = invoice_qs.count()
    unpaid_count = invoice_qs.filter(status="unpaid").count()
    paid_count = invoice_qs.filter(status="paid").count()
    partial_count = invoice_qs.filter(status="partial_paid").count()
    due_count = invoice_qs.filter(status="due").count()

    # Revenue this month from Income records
    income_mtd_agg = Income.objects.filter(
        date__date__gte=first_of_month
    ).aggregate(total=Sum("actual_received"))
    revenue_mtd = float(income_mtd_agg["total"] or 0)

    # Outstanding dues across all member accounts
    outstanding_agg = MemberAccount.objects.aggregate(
        total=Sum("overdue_amount")
    )
    total_outstanding_dues = float(outstanding_agg["total"] or 0)

    # Sales MTD
    sales_mtd_agg = Sale.objects.filter(
        sales_date__gte=first_of_month
    ).aggregate(total=Sum("total_amount"))
    sales_mtd = float(sales_mtd_agg["total"] or 0)

    # Top 5 members by overdue amount
    top_debtors = list(
        MemberAccount.objects.filter(overdue_amount__gt=0)
        .select_related("member")
        .order_by("-overdue_amount")
        .values(
            "member__first_name",
            "member__last_name",
            "member__member_ID",
            "overdue_amount",
        )[:5]
    )
    for d in top_debtors:
        d["overdue_amount"] = float(d["overdue_amount"])

    # Invoice status breakdown for pie chart
    invoice_status_chart = [
        {"status": "paid", "count": paid_count},
        {"status": "unpaid", "count": unpaid_count},
        {"status": "partial_paid", "count": partial_count},
        {"status": "due", "count": due_count},
    ]

    return {
        "kpi": {
            "revenue_mtd": revenue_mtd,
            "sales_mtd": sales_mtd,
            "total_outstanding_dues": total_outstanding_dues,
            "total_invoices": total_invoices,
            "unpaid_invoices": unpaid_count,
            "paid_invoices": paid_count,
        },
        "invoice_status_chart": invoice_status_chart,
        "top_debtors": top_debtors,
    }


def _build_restaurant_section():
    """
    Requires: restaurant:view_menu
    Returns today's order KPIs, status breakdown, hourly chart,
    per-restaurant revenue today, and top 5 ordered items today.
    """
    today = now().date()

    # Today's orders
    orders_today_qs = RestaurantOrder.objects.filter(created_at__date=today)

    total_today = orders_today_qs.count()
    in_progress = orders_today_qs.filter(
        status__in=["confirmed", "preparing", "ready"]
    ).count()
    billed_today = orders_today_qs.filter(status="billed").count()
    cancelled_today = orders_today_qs.filter(status="cancelled").count()
    served_today = orders_today_qs.filter(status="served").count()

    # Revenue today (billed orders only)
    revenue_agg = orders_today_qs.filter(status="billed").aggregate(
        total=Sum("total_amount")
    )
    revenue_today = float(revenue_agg["total"] or 0)

    # Status breakdown for donut chart
    status_chart = [
        {"status": s, "count": orders_today_qs.filter(status=s).count()}
        for s in ["confirmed", "preparing", "ready", "served", "billed", "cancelled"]
    ]

    # Hourly order volume for today (bar chart)
    hourly_qs = (
        orders_today_qs
        .annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hourly_chart = [
        {
            "hour": row["hour"].strftime("%H:00") if row["hour"] else "Unknown",
            "orders": row["count"],
        }
        for row in hourly_qs
    ]

    # Revenue per restaurant today
    restaurant_revenue_qs = (
        orders_today_qs.filter(status="billed")
        .values("restaurant__name")
        .annotate(revenue=Sum("total_amount"))
        .order_by("-revenue")
    )
    restaurant_revenue = [
        {
            "restaurant": row["restaurant__name"],
            "revenue": float(row["revenue"] or 0),
        }
        for row in restaurant_revenue_qs
    ]

    # Top 5 ordered items today (by line item count)
    from restaurant.models import RestaurantOrderItem
    top_items_qs = (
        RestaurantOrderItem.objects.filter(order__created_at__date=today)
        .values("item__name")
        .annotate(times_ordered=Sum("quantity"))
        .order_by("-times_ordered")[:5]
    )
    top_items = [
        {"item": row["item__name"], "times_ordered": row["times_ordered"]}
        for row in top_items_qs
    ]

    return {
        "kpi": {
            "orders_today": total_today,
            "in_progress": in_progress,
            "billed_today": billed_today,
            "cancelled_today": cancelled_today,
            "served_today": served_today,
            "revenue_today": revenue_today,
        },
        "status_chart": status_chart,
        "hourly_chart": hourly_chart,
        "restaurant_revenue": restaurant_revenue,
        "top_items_today": top_items,
    }


def _build_outlet_section():
    """
    Requires: outlet:view_menu
    Returns today's outlet order KPIs and per-outlet breakdown.
    """
    from outlet.models import Outlet, OutletOrder

    today = now().date()

    # Check if OutletOrder exists (import safely)
    try:
        orders_today_qs = OutletOrder.objects.filter(created_at__date=today)
        total_today = orders_today_qs.count()
        active_now = orders_today_qs.filter(
            status__in=["confirmed", "preparing", "ready"]
        ).count()
        revenue_agg = orders_today_qs.filter(status="billed").aggregate(
            total=Sum("total_amount")
        )
        revenue_today = float(revenue_agg["total"] or 0)

        # Per-outlet breakdown
        per_outlet_qs = (
            orders_today_qs.filter(status="billed")
            .values("outlet__name", "outlet__outlet_type")
            .annotate(
                order_count=Count("id"),
                revenue=Sum("total_amount"),
            )
            .order_by("-revenue")
        )
        per_outlet = [
            {
                "outlet": row["outlet__name"],
                "type": row["outlet__outlet_type"],
                "orders": row["order_count"],
                "revenue": float(row["revenue"] or 0),
            }
            for row in per_outlet_qs
        ]
    except Exception:
        # OutletOrder might not be imported yet
        total_today = 0
        active_now = 0
        revenue_today = 0.0
        per_outlet = []

    total_outlets = Outlet.objects.filter(is_active=True).count()
    open_outlets = Outlet.objects.filter(status="open", is_active=True).count()

    return {
        "kpi": {
            "total_outlets": total_outlets,
            "open_outlets": open_outlets,
            "orders_today": total_today,
            "active_orders_now": active_now,
            "revenue_today": revenue_today,
        },
        "per_outlet_today": per_outlet,
    }


def _build_reservations_section():
    """
    Requires: reservation:view
    Returns today's reservation KPIs, resource status board,
    and upcoming 10 reservations.
    """
    from reservation.models import Reservation, ReservableResource

    now_dt = now()
    today = now_dt.date()
    today_start = timezone.make_aware(
        datetime.datetime.combine(today, datetime.time.min)
    )
    today_end = timezone.make_aware(
        datetime.datetime.combine(today, datetime.time.max)
    )

    today_qs = Reservation.objects.filter(
        start_time__date=today
    )
    total_today = today_qs.count()
    confirmed_today = today_qs.filter(status="confirmed").count()
    pending_payment = today_qs.filter(status="pending_payment").count()
    cancelled_today = today_qs.filter(status="cancelled").count()

    # Currently active: confirmed and now within the time slot
    active_now = Reservation.objects.filter(
        status="confirmed",
        start_time__lte=now_dt,
        end_time__gte=now_dt,
    ).count()

    # Upcoming (next 2 hours)
    two_hours_later = now_dt + datetime.timedelta(hours=2)
    upcoming_count = Reservation.objects.filter(
        status="confirmed",
        start_time__gte=now_dt,
        start_time__lte=two_hours_later,
    ).count()

    # Resource status board
    resources = list(
        ReservableResource.objects.filter(is_active=True).values(
            "id", "name", "resource_type", "status", "capacity",
            "opening_time", "closing_time"
        )
    )
    for r in resources:
        r["opening_time"] = str(r["opening_time"]) if r["opening_time"] else None
        r["closing_time"] = str(r["closing_time"]) if r["closing_time"] else None
        # bookings count for today
        r["bookings_today"] = Reservation.objects.filter(
            resource_id=r["id"], start_time__date=today,
            status__in=["pending_payment", "confirmed"]
        ).count()

    # Next 10 upcoming reservations
    upcoming_list = list(
        Reservation.objects.filter(
            start_time__gte=now_dt,
            status__in=["pending_payment", "confirmed"],
        )
        .select_related("resource", "member")
        .order_by("start_time")
        .values(
            "reservation_number",
            "status",
            "start_time",
            "end_time",
            "resource__name",
            "member__first_name",
            "member__last_name",
            "member__member_ID",
            "advance_paid",
        )[:10]
    )
    for r in upcoming_list:
        r["start_time"] = r["start_time"].isoformat() if r["start_time"] else None
        r["end_time"] = r["end_time"].isoformat() if r["end_time"] else None

    return {
        "kpi": {
            "total_today": total_today,
            "confirmed_today": confirmed_today,
            "pending_payment": pending_payment,
            "cancelled_today": cancelled_today,
            "active_now": active_now,
            "upcoming_2h": upcoming_count,
        },
        "resource_status": resources,
        "upcoming_reservations": upcoming_list,
    }


def _build_events_section():
    """
    Requires: event:view
    Returns event KPIs, upcoming events list.
    """
    today = now().date()

    upcoming_events = Event.objects.filter(
        start_date__date__gte=today, is_active=True
    ).count()
    events_this_month = Event.objects.filter(
        start_date__date__gte=today.replace(day=1),
        is_active=True,
    ).count()
    total_events = Event.objects.filter(is_active=True).count()

    # Upcoming events list (next 5)
    upcoming_list = list(
        Event.objects.filter(start_date__date__gte=today, is_active=True)
        .order_by("start_date")
        .values(
            "id", "title", "start_date", "end_date",
            "status", "event_type", "registration_deadline"
        )[:5]
    )
    for e in upcoming_list:
        e["start_date"] = e["start_date"].isoformat() if e["start_date"] else None
        e["end_date"] = e["end_date"].isoformat() if e["end_date"] else None
        e["registration_deadline"] = (
            e["registration_deadline"].isoformat()
            if e["registration_deadline"]
            else None
        )

    # Event status breakdown
    status_chart = [
        {"status": s, "count": Event.objects.filter(status=s, is_active=True).count()}
        for s in ["planned", "ongoing", "completed", "cancelled"]
    ]

    return {
        "kpi": {
            "total_active_events": total_events,
            "upcoming_events": upcoming_events,
            "events_this_month": events_this_month,
        },
        "upcoming_events_list": upcoming_list,
        "status_chart": status_chart,
    }


def _build_attendance_section():
    """
    Requires: attendance:view_records
    Returns live presence count, today's check-in/out KPIs,
    hourly traffic chart, recent feed (last 10 events).
    """
    from attendance.models import AttendanceRecord

    now_dt = now()
    today = now_dt.date()

    today_records = AttendanceRecord.objects.filter(check_in__date=today)

    # Currently inside = checked in today, not yet checked out
    currently_inside = AttendanceRecord.objects.filter(
        check_in__date=today, check_out__isnull=True
    ).count()
    members_inside = AttendanceRecord.objects.filter(
        check_in__date=today, check_out__isnull=True, subject_type="member"
    ).count()
    staff_inside = AttendanceRecord.objects.filter(
        check_in__date=today, check_out__isnull=True, subject_type="staff"
    ).count()

    total_checkins_today = today_records.count()
    total_checkouts_today = today_records.filter(
        check_out__isnull=False
    ).count()
    guests_today = today_records.filter(subject_type="guest").count()

    # Hourly traffic (check-ins per hour today)
    hourly_qs = (
        today_records
        .annotate(hour=TruncHour("check_in"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hourly_chart = [
        {
            "hour": row["hour"].strftime("%H:00") if row["hour"] else "Unknown",
            "checkins": row["count"],
        }
        for row in hourly_qs
    ]

    # Recent activity feed (last 10 check-in events)
    recent_feed_qs = (
        AttendanceRecord.objects.filter(check_in__date=today)
        .select_related("member", "staff__user", "guest")
        .order_by("-check_in")[:10]
    )
    recent_feed = []
    for rec in recent_feed_qs:
        name = "Unknown"
        if rec.subject_type == "member" and rec.member:
            name = f"{rec.member.first_name} {rec.member.last_name}".strip()
        elif rec.subject_type == "staff" and rec.staff:
            name = rec.staff.user.get_full_name() or rec.staff.user.username
        elif rec.subject_type == "guest" and rec.guest:
            name = rec.guest.name
        recent_feed.append({
            "subject_type": rec.subject_type,
            "name": name,
            "check_in": rec.check_in.isoformat(),
            "check_out": rec.check_out.isoformat() if rec.check_out else None,
            "is_inside": rec.check_out is None,
        })

    return {
        "kpi": {
            "currently_inside": currently_inside,
            "members_inside": members_inside,
            "staff_inside": staff_inside,
            "total_checkins_today": total_checkins_today,
            "total_checkouts_today": total_checkouts_today,
            "guests_today": guests_today,
        },
        "hourly_chart": hourly_chart,
        "recent_feed": recent_feed,
    }


def _build_payroll_section():
    """
    Requires: payroll:view_structures
    Returns payroll run status for current month, staff count,
    pending payslips, and active loans.
    """
    from payroll.models import PayrollRun, Payslip, StaffLoan
    from attendance.models import StaffProfile

    today = now().date()
    current_month = today.month
    current_year = today.year

    total_staff = StaffProfile.objects.filter(is_active=True).count()

    # Current month payroll run
    current_run = PayrollRun.objects.filter(
        period_year=current_year, period_month=current_month
    ).first()
    payroll_run_status = current_run.status if current_run else "not_run"
    payroll_run_total = float(current_run.total_amount) if current_run else 0.0

    # Pending payslips (generated but not paid)
    pending_payslips = Payslip.objects.filter(status="generated").count()

    # Active loans
    active_loans_agg = StaffLoan.objects.filter(
        status="active"
    ).aggregate(
        count=Count("id"),
        total_outstanding=Sum("outstanding"),
    )
    active_loans_count = active_loans_agg["count"] or 0
    total_loan_outstanding = float(active_loans_agg["total_outstanding"] or 0)

    # Recent payroll runs (last 5)
    recent_runs = list(
        PayrollRun.objects.filter(is_active=True)
        .order_by("-period_year", "-period_month")[:5]
        .values("id", "name", "period_month", "period_year", "status", "total_amount")
    )
    for r in recent_runs:
        r["total_amount"] = float(r["total_amount"])

    # Staff loans list (top 5 active by outstanding)
    active_loans_list = list(
        StaffLoan.objects.filter(status="active", outstanding__gt=0, is_active=True)
        .select_related("staff__user")
        .order_by("-outstanding")[:5]
        .values("id", "principal", "outstanding", "monthly_deduction", "staff__user__first_name", "staff__user__last_name")
    )
    for l in active_loans_list:
        l["principal"] = float(l["principal"])
        l["outstanding"] = float(l["outstanding"])
        l["monthly_deduction"] = float(l["monthly_deduction"])

    return {
        "kpi": {
            "total_staff": total_staff,
            "current_month_payroll_status": payroll_run_status,
            "current_month_payroll_total": payroll_run_total,
            "pending_payslips": pending_payslips,
            "active_loans_count": active_loans_count,
            "total_loan_outstanding": total_loan_outstanding,
        },
        "recent_runs": recent_runs,
        "active_loans_list": active_loans_list,
    }


def _build_vendor_section():
    """
    Requires: vendor:view
    Returns vendor KPIs and pending offer count.
    """
    from vendor.models import Vendor, VendorServiceOffer, VendorServiceCategory, VendorPayment
    from product.models import Product

    total_vendors = Vendor.objects.filter(is_active=True).count()
    active_contracts = VendorServiceOffer.objects.filter(
        status="selected", is_active=True
    ).count()
    pending_offers = VendorServiceOffer.objects.filter(
        status="offered", is_active=True
    ).count()
    total_categories = VendorServiceCategory.objects.filter(is_active=True).count()
    total_products = Product.objects.filter(is_active=True).count()

    # Pending offers list
    pending_offers_list = list(
        VendorServiceOffer.objects.filter(status="offered", is_active=True)
        .select_related("vendor", "category")
        .order_by("-created_at")[:5]
        .values(
            "id", "title", "price", "billing_cycle",
            "vendor__name", "category__name", "created_at"
        )
    )
    for p in pending_offers_list:
        p["price"] = float(p["price"])
        p["created_at"] = p["created_at"].isoformat() if p["created_at"] else None

    # Recent payments
    recent_payments = list(
        VendorPayment.objects.filter(is_active=True)
        .select_related("offer__vendor")
        .order_by("-paid_on")[:5]
        .values("amount", "paid_on", "reference", "payment_type", "offer__vendor__name")
    )
    for rp in recent_payments:
        rp["amount"] = float(rp["amount"])
        rp["paid_on"] = rp["paid_on"].isoformat() if rp["paid_on"] else None

    return {
        "kpi": {
            "total_vendors": total_vendors,
            "active_contracts": active_contracts,
            "pending_offers": pending_offers,
            "total_service_categories": total_categories,
            "total_active_products": total_products,
        },
        "pending_offers_list": pending_offers_list,
        "recent_payments": recent_payments,
    }


def _build_system_section(user):
    """
    Requires: group:view (admin-level)
    Returns platform user/group counts, active today, recent audit log.
    """
    today = now().date()

    total_users = User.objects.count()
    staff_users = User.objects.filter(role="STAFF").count()
    member_users = User.objects.filter(role="MEMBER").count()
    total_groups = GroupModel.objects.count()

    # Unique users active today (from activity log)
    active_today = (
        ActivityLog.objects
        .filter(timestamp__date=today)
        .exclude(user=None)
        .values("user")
        .distinct()
        .count()
    )

    # Recent audit events (last 10)
    recent_logs_qs = (
        ActivityLog.objects
        .select_related("user")
        .order_by("-timestamp")[:10]
    )
    recent_logs = [
        {
            "user": log.user.username if log.user else "System",
            "verb": log.verb,
            "path": log.path,
            "severity": log.severity_level,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in recent_logs_qs
    ]

    return {
        "kpi": {
            "total_users": total_users,
            "staff_users": staff_users,
            "member_users": member_users,
            "total_groups": total_groups,
            "active_today": active_today,
        },
        "recent_audit_log": recent_logs,
    }


# ---------------------------------------------------------------------------
# VIEW 1 — Main summary (static / semi-static, cache-friendly)
# ---------------------------------------------------------------------------

class DashboardSummaryView(APIView):
    """
    Single endpoint that returns every section the requesting user
    is permitted to see.  No section is computed unless the user
    holds the required permission — zero wasted DB work.

    GET /api/dashboard/v1/summary/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            perms = _get_user_permissions(user)
            data = {}

            # ── Overview section (Role-tailored 360° view) ──────────────
            data["overview"] = _build_overview_section(user, perms)

            # ── Member section ──────────────────────────────────────────
            if _has(perms, "member:view"):
                data["member"] = _build_member_section(request.GET)

            # ── Finance section ─────────────────────────────────────────
            if _has(perms, "member_financial:view_invoices"):
                data["finance"] = _build_finance_section()

            # ── Restaurant section ──────────────────────────────────────
            if _has(perms, "restaurant:view_menu", "restaurant_management"):
                data["restaurant"] = _build_restaurant_section()

            # ── Outlet section ──────────────────────────────────────────
            if _has(perms, "outlet:view_menu", "outlet_operations"):
                data["outlet"] = _build_outlet_section()

            # ── Reservations section ────────────────────────────────────
            if _has(perms, "reservation:view"):
                data["reservations"] = _build_reservations_section()

            # ── Events section ──────────────────────────────────────────
            if _has(perms, "event:view", "event_management"):
                data["events"] = _build_events_section()

            # ── Attendance section ──────────────────────────────────────
            if _has(perms, "attendance:view_records"):
                data["attendance"] = _build_attendance_section()

            # ── Payroll section ─────────────────────────────────────────
            if _has(perms, "payroll:view_structures"):
                data["payroll"] = _build_payroll_section()

            # ── Vendor / procurement section ────────────────────────────
            if _has(perms, "vendor:view"):
                data["vendor"] = _build_vendor_section()

            # ── System / admin section ──────────────────────────────────
            if _has(perms, "group:view"):
                data["system"] = _build_system_section(user)

            return Response({
                "code": 200,
                "status": "success",
                "message": "Dashboard summary",
                "sections": list(data.keys()),   # tells frontend what to render
                "data": data,
            }, status=200)

        except Exception as e:
            logger.exception("DashboardSummaryView error: %s", e)
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Error building dashboard summary",
                "errors": {"server_error": [str(e)]},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# VIEW 2 — Live feed (polled every 30 s for operational roles only)
# ---------------------------------------------------------------------------

class DashboardLiveView(APIView):
    """
    Lightweight endpoint for real-time data only.
    Frontend polls this every 30 seconds; only sections the user
    has permission for are returned.

    GET /api/dashboard/v1/live/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            perms = _get_user_permissions(user)
            data = {}
            today = now().date()

            # ── Live restaurant KDS feed ────────────────────────────────
            if _has(perms, "restaurant:view_menu", "restaurant:kitchen_update",
                    "restaurant_management"):
                live_orders_qs = (
                    RestaurantOrder.objects
                    .filter(
                        status__in=["confirmed", "preparing", "ready", "served"],
                        created_at__date=today,
                    )
                    .select_related("restaurant", "member")
                    .order_by("created_at")[:20]
                )
                data["restaurant_live_orders"] = [
                    {
                        "order_number": o.order_number,
                        "status": o.status,
                        "restaurant": o.restaurant.name,
                        "member_name": f"{o.member.first_name} {o.member.last_name}".strip(),
                        "total_amount": float(o.total_amount),
                        "created_at": o.created_at.isoformat(),
                        "serve_location": o.serve_location,
                    }
                    for o in live_orders_qs
                ]

            # ── Live attendance / gate feed ─────────────────────────────
            if _has(perms, "attendance:view_records"):
                from attendance.models import AttendanceRecord
                currently_inside = AttendanceRecord.objects.filter(
                    check_in__date=today, check_out__isnull=True
                ).count()

                recent_qs = (
                    AttendanceRecord.objects
                    .filter(check_in__date=today)
                    .select_related("member", "staff__user", "guest")
                    .order_by("-check_in")[:10]
                )
                live_feed = []
                for rec in recent_qs:
                    name = "Unknown"
                    if rec.subject_type == "member" and rec.member:
                        name = f"{rec.member.first_name} {rec.member.last_name}".strip()
                    elif rec.subject_type == "staff" and rec.staff:
                        name = rec.staff.user.get_full_name() or rec.staff.user.username
                    elif rec.subject_type == "guest" and rec.guest:
                        name = rec.guest.name
                    live_feed.append({
                        "subject_type": rec.subject_type,
                        "name": name,
                        "check_in": rec.check_in.isoformat(),
                        "check_out": rec.check_out.isoformat() if rec.check_out else None,
                        "is_inside": rec.check_out is None,
                    })

                data["attendance"] = {
                    "currently_inside": currently_inside,
                    "recent_feed": live_feed,
                }

            return Response({
                "code": 200,
                "status": "success",
                "message": "Live dashboard data",
                "timestamp": now().isoformat(),
                "data": data,
            }, status=200)

        except Exception as e:
            logger.exception("DashboardLiveView error: %s", e)
            return Response({
                "code": 500,
                "status": "failed",
                "message": "Error building live dashboard data",
                "errors": {"server_error": [str(e)]},
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Legacy views — kept as-is so existing frontend doesn't break
# ---------------------------------------------------------------------------

from .utils.filters import MemberFilter
from account.models import GroupModel


class DashboardCardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            total_member = Member.objects.all()
            total_active_member = Member.objects.filter(
                membership_status__name__iexact="active")
            total_pending_member = Member.objects.filter(
                membership_status__name__iexact="pending")
            total_restaurants = Restaurant.active_objects.all()
            total_products = Product.objects.filter(is_active=True)
            total_events = Event.objects.filter(is_active=True)

            total_member_filterset = MemberFilter(
                request.GET, queryset=total_member)
            total_active_member_filterset = MemberFilter(
                request.GET, queryset=total_active_member)
            total_pending_member_filterset = MemberFilter(
                request.GET, queryset=total_pending_member)
            total_restaurants_filterset = MemberFilter(
                request.GET, queryset=total_restaurants)
            total_products_filterset = MemberFilter(
                request.GET, queryset=total_products)
            total_events_filterset = MemberFilter(
                request.GET, queryset=total_events)

            total_member = total_member_filterset.qs
            total_active_member = total_active_member_filterset.qs
            total_pending_member = total_pending_member_filterset.qs
            total_restaurants = total_restaurants_filterset.qs
            total_products = total_products_filterset.qs
            total_events = total_events_filterset.qs

            return Response({
                "code": 200,
                "status": "success",
                "message": "All dashboard card data",
                "data": {
                    "total_member_count": total_member.count(),
                    "total_active_member_count": total_active_member.count(),
                    "total_pending_member_count": total_pending_member.count(),
                    "total_restaurants_count": total_restaurants.count(),
                    "total_products_count": total_products.count(),
                    "total_events_count": total_events.count(),
                }
            }, status=200)

        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DashboardChartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = (
                Member.objects.values("membership_type__name")
                .annotate(
                    active=Count("id", filter=Q(
                        membership_status__name__iexact="active")),
                    pending=Count("id", filter=Q(
                        membership_status__name__iexact="pending")),
                )
                .order_by("membership_type__name")
            )
            data = [
                {
                    "membership_type": row["membership_type__name"],
                    "active": row["active"],
                    "pending": row["pending"],
                }
                for row in qs
            ]
            return Response({
                "code": 200,
                "status": "success",
                "message": "chart data",
                "data": data
            }, status=200)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DashboardPieChartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            qs = Member.objects.values("membership_type__name").annotate(
                count=Count("id")).order_by("membership_type__name")
            data = [
                {"name": row["membership_type__name"], "value": row["count"]}
                for row in qs
            ]
            return Response({
                "code": 200,
                "status": "success",
                "message": "chart data",
                "data": data
            }, status=200)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DashBoardKPICard(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            today = now().date()
            group_count = GroupModel.objects.all().count()
            user_count = User.objects.all().count()
            unique_users_today = (
                ActivityLog.objects
                .filter(timestamp__date=today)
                .values("user")
                .exclude(user=None)
                .distinct()
                .count()
            )
            return Response({
                "code": 200,
                "status": "success",
                "message": "All dashboard card data",
                "data": {
                    "group_count": group_count,
                    "user_count": user_count,
                    "active_user_today": unique_users_today,
                }
            }, status=200)
        except Exception as e:
            logger.exception(str(e))
            return Response({
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Error occurred",
                "status": "failed",
                "errors": {"server_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
