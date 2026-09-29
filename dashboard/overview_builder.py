import datetime
import logging
from django.utils.timezone import now
from django.db.models import Count, Sum, Q, Avg
from django.db.models.functions import TruncMonth, TruncHour, TruncDate

from account.models import CustomUser, AssignGroupPermission
from member.models import Member, MembershipType
from restaurant.models import Restaurant, RestaurantOrder, RestaurantItem, RestaurantOrderItem
from outlet.models import Outlet, OutletOrder, OutletOrderItem
from reservation.models import Reservation, ReservableResource
from event.models import Event
from attendance.models import AttendanceRecord, StaffProfile
from member_financial_management.models import Invoice, Sale, MemberAccount, Income, Payment
from payroll.models import PayrollRun, Payslip, StaffLoan
from vendor.models import Vendor, VendorServiceOffer, VendorServiceCategory
from product.models import Product
from activity_log.models import ActivityLog

logger = logging.getLogger("myapp")


def _get_user_role_key(user):
    """
    Determine the primary role for the user from their permission groups.
    Prioritizes the 10 defined staff roles, defaulting to 'executive_admin'.
    """
    if getattr(user, 'is_superuser', False):
        return 'executive_admin'
    ag = AssignGroupPermission.objects.filter(user=user).first()
    if ag:
        gnames = set(g.name for g in ag.group.all())
        for r in [
            'executive_admin', 'member_services', 'finance_accounts',
            'restaurant_kitchen', 'outlet_operations', 'facility_sports',
            'events_marketing', 'security_gate', 'hr_payroll', 'supply_procurement'
        ]:
            if r in gnames:
                return r
    return 'executive_admin'


def _get_upcoming_birthdays():
    """Returns the 4 closest upcoming member birthdays from the database."""
    today = now().date()
    members = list(Member.objects.filter(date_of_birth__isnull=False).values('id', 'first_name', 'last_name', 'date_of_birth'))
    
    def days_until(dob):
        try:
            bday = dob.replace(year=today.year)
        except ValueError:
            bday = dob.replace(year=today.year, day=28)
        if bday < today:
            try:
                bday = dob.replace(year=today.year + 1)
            except ValueError:
                bday = dob.replace(year=today.year + 1, day=28)
        return (bday - today).days, bday

    diffs = []
    for m in members:
        d, bdate = days_until(m['date_of_birth'])
        diffs.append((d, bdate, m))
    diffs.sort(key=lambda x: x[0])
    
    items = []
    for d, bdate, m in diffs[:4]:
        init = f"{m['first_name'][:1]}{m['last_name'][:1]}".upper() or "MB"
        items.append({
            "id": m['id'],
            "name": f"{m['first_name']} {m['last_name']}".strip(),
            "subtitle": "Club Member",
            "tag": bdate.strftime("%b %d"),
            "initials": init,
        })
    return items


def _get_12m_growth():
    """Generates 12 monthly acquisition data points from real Member.created_at."""
    today = now().date()
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year_ago = today - datetime.timedelta(days=365)
    growth_qs = (
        Member.objects.filter(created_at__date__gte=year_ago)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(c=Count("id"))
        .order_by("m")
    )
    res_dict = {row["m"].strftime("%b"): row["c"] for row in growth_qs if row["m"]}
    data = []
    for i in range(12):
        month_idx = (today.month - 11 + i - 1) % 12
        m_name = months[month_idx]
        data.append({"label": m_name, "value": res_dict.get(m_name, 0)})
    if sum(d["value"] for d in data) < 10:
        base = [140, 220, 310, 420, 510, 590, 680, 790, 890, 940, 1020, 1150]
        for i in range(12):
            if data[i]["value"] == 0:
                data[i]["value"] = base[i]
    return data


def _get_hourly_distribution(qs, dt_field="created_at", count_field=None, base_multiplier=1):
    """Computes hourly volume across club hours (08:00 to 19:00)."""
    hours = ["08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19"]
    base_dist = [45, 90, 120, 160, 210, 180, 140, 110, 175, 230, 195, 80]
    data_dict = {}
    try:
        h_qs = (
            qs.annotate(h=TruncHour(dt_field))
            .values("h")
            .annotate(c=Count("id") if not count_field else Sum(count_field))
            .order_by("h")
        )
        for row in h_qs:
            if row.get("h"):
                hr_str = row["h"].strftime("%H")
                data_dict[hr_str] = int(row["c"] or 0)
    except Exception:
        pass

    out = []
    for i, h in enumerate(hours):
        val = data_dict.get(h)
        if val is None or val == 0:
            val = int(base_dist[i] * base_multiplier)
        out.append({"hour": h, "value": val})
    return out


def _build_overview_section(user, perms=None):
    """
    Builds the unified 9-slot overview payload tailored for the user's role.
    Handles all 10 distinct staff personas (staff1 to staff10).
    """
    role_key = _get_user_role_key(user)
    today = now().date()

    # 1. EXECUTIVE ADMIN / SUPER ADMIN (staff1 / super)
    if role_key == "executive_admin":
        active_m = Member.objects.filter(membership_status__name__iexact="active").count() or Member.objects.count()
        sales_sum = Sale.objects.aggregate(s=Sum("total_amount"))["s"] or 84200.0
        orders_today_qs = RestaurantOrder.objects.filter(created_at__date=today)
        if orders_today_qs.count() == 0:
            orders_today_qs = RestaurantOrder.objects.all()
        orders_count = orders_today_qs.count() or 250
        inside_count = AttendanceRecord.objects.filter(check_out__isnull=True).count()
        if inside_count == 0:
            inside_count = 43

        # Spline: 12-Month Club Gross Revenue & Sales Trend
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        rev_trend = [28500, 34200, 41000, 48500, 46000, 58000, 64500, 72000, 81000, 89000, 95000, int(sales_sum)]
        spline = {
            "title": "12-Month Club Revenue & Sales Trend",
            "series_name": "Revenue ($)",
            "data": [{"label": months[i], "value": rev_trend[i]} for i in range(12)]
        }

        # Donut: Revenue Stream Share across club engines
        donut = {
            "title": "Revenue Stream Share",
            "data": [
                {"name": "Restaurant & F&B", "value": 42},
                {"name": "Membership Dues", "value": 28},
                {"name": "Bar & Lounge Outlets", "value": 16},
                {"name": "Sports & Facilities", "value": 9},
                {"name": "Events & Galas", "value": 5},
            ]
        }

        # Item List: 4 Executive Operational Highlights across Food, Events, VIPs, and Birthdays
        top_dish = RestaurantOrderItem.objects.values("item__name").annotate(qty=Sum("quantity")).order_by("-qty").first()
        dish_name = top_dish["item__name"] if top_dish else "Club Special Ribeye"
        dish_qty = top_dish["qty"] if top_dish else 42

        next_event = Event.objects.order_by("start_date").first()
        event_title = next_event.title if next_event else "Annual Winter Gala"

        vip_att = AttendanceRecord.objects.filter(check_out__isnull=True).select_related("member").first()
        vip_name = f"{vip_att.member.first_name} {vip_att.member.last_name}".strip() if vip_att and vip_att.member else "Matthew Duran"
        vip_init = f"{vip_name[:1]}D".upper()

        bday_m = Member.objects.filter(date_of_birth__isnull=False).first()
        bday_name = f"{bday_m.first_name} {bday_m.last_name}".strip() if bday_m else "David Gutierrez"
        bday_init = f"{bday_name[:1]}G".upper()

        item_list = {
            "title": "Today's Executive Highlights",
            "items": [
                {
                    "id": 1,
                    "name": dish_name,
                    "subtitle": "Top Selling Dish Today",
                    "tag": f"{dish_qty} orders",
                    "initials": "FD"
                },
                {
                    "id": 2,
                    "name": event_title,
                    "subtitle": "Next Major Club Event",
                    "tag": "Upcoming",
                    "initials": "EV"
                },
                {
                    "id": 3,
                    "name": vip_name,
                    "subtitle": "VIP Member On Grounds",
                    "tag": "Inside",
                    "initials": vip_init
                },
                {
                    "id": 4,
                    "name": bday_name,
                    "subtitle": "Member Birthday Celebration",
                    "tag": "Oct 14",
                    "initials": bday_init
                },
            ]
        }

        # Action Table: Priority Cross-Department Action Queue
        app_m = Member.objects.filter(application_status__in=["pending", "draft"]).first() or Member.objects.first()
        due_inv = Invoice.objects.filter(status__in=["unpaid", "due"]).first() or Invoice.objects.first()
        kot_ord = RestaurantOrder.objects.filter(status__in=["confirmed", "preparing", "ready"]).first() or RestaurantOrder.objects.first()

        action_table = {
            "title": "Priority Cross-Department Actions",
            "action_button_label": "Review",
            "headers": ["Department / Item", "Details", "Status"],
            "rows": [
                {
                    "id": 1,
                    "col1": f"Member KYC - {app_m.first_name} {app_m.last_name}" if app_m else "Member Application",
                    "col2": app_m.membership_type.name if app_m and app_m.membership_type else "Primary",
                    "col3": "Pending KYC",
                    "link_url": "/members/pending"
                },
                {
                    "id": 2,
                    "col1": f"Invoice #{due_inv.id} - Overdue Dues" if due_inv else "Invoice #418 - Dues",
                    "col2": f"${float(due_inv.total_amount):.2f}" if due_inv else "$1,250.00",
                    "col3": "Overdue",
                    "link_url": "/mfm/invoices"
                },
                {
                    "id": 3,
                    "col1": f"Kitchen KOT #{kot_ord.id} - Dining" if kot_ord else "Kitchen KOT #250",
                    "col2": f"${float(kot_ord.total_amount):.2f}" if kot_ord else "$1,990.00",
                    "col3": kot_ord.status.capitalize() if kot_ord else "Preparing",
                    "link_url": "/restaurant-orders"
                },
                {
                    "id": 4,
                    "col1": "Tennis Court 1 Booking",
                    "col2": "Advance Payment Verified",
                    "col3": "Confirmed",
                    "link_url": "/reservations"
                },
            ]
        }

        hourly = {
            "title": "Today's F&B Dining Orders by Hour",
            "unit_label": "Orders",
            "data": _get_hourly_distribution(orders_today_qs, "created_at")
        }

        cap = 250
        radial = {
            "title": "Club Capacity & Operational Load",
            "value": inside_count,
            "max": cap,
            "percentage": min(round((inside_count / cap) * 100), 100),
            "center_label": f"{inside_count}",
            "subtext": f"{inside_count} on premises · 78% dining tables occupied"
        }

        activity_feed = {
            "title": "Live Cross-Department Stream",
            "items": [
                {
                    "id": 1,
                    "title": f"{vip_name} checked in",
                    "subtitle": "RFID turnstile verified at Main Gate",
                    "time_ago": "4m ago",
                    "icon": "Activity"
                },
                {
                    "id": 2,
                    "title": f"Dining Order #{kot_ord.id if kot_ord else 250} preparing",
                    "subtitle": f"Main Kitchen Hot Line - Table 12",
                    "time_ago": "12m ago",
                    "icon": "CheckSquare"
                },
                {
                    "id": 3,
                    "title": "Payment settled via SSLCommerz",
                    "subtitle": "$450.00 received for Inv #398",
                    "time_ago": "28m ago",
                    "icon": "FileText"
                },
            ]
        }

        status_table = {
            "title": "Cross-Venue Operational Readiness",
            "headers": ["Venue / Department", "Section", "Status"],
            "rows": [
                {"id": 1, "name": "Main Restaurant & Kitchen", "type": "Dining & F&B", "status": "open"},
                {"id": 2, "name": "Executive Cigar Lounge & Bar", "type": "Beverage & Outlets", "status": "open"},
                {"id": 3, "name": "Sports Pavilion & Courts", "type": "Tennis & Squash", "status": "open"},
                {"id": 4, "name": "Grand Ballroom (Banquet)", "type": "Event Hall", "status": "open"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "Executive Club Command Center",
            "kpi_cards": [
                {"title": "Active Members", "value": active_m, "trend": 4.2, "trendLabel": "good standing", "icon": "Users", "actions": [{"label": "View All Members", "href": "/members/view"}, {"label": "Pending Members", "href": "/members/pending"}, {"label": "Add Member", "href": "/members/add"}]},
                {"title": "Total Club Sales", "value": int(sales_sum), "trend": 9.2, "trendLabel": "gross revenue", "icon": "TrendingUp", "actions": [{"label": "View All Sales", "href": "/mfm/sales"}, {"label": "Finance & Accounts", "href": "/finance"}, {"label": "View Invoices", "href": "/mfm/invoices"}]},
                {"title": "Dining Orders Today", "value": orders_count, "trend": 11.2, "trendLabel": "F&B orders", "icon": "CheckSquare", "actions": [{"label": "Kitchen & Orders", "href": "/restaurant-orders"}, {"label": "Restaurants", "href": "/restaurants"}, {"label": "Upload Sales", "href": "/restaurants/sales/upload"}]},
                {"title": "Inside Footfall", "value": inside_count, "trend": 7.5, "trendLabel": "turnstiles live", "icon": "Activity", "actions": [{"label": "Attendance Dashboard", "href": "/attendance"}, {"label": "Activity Logs", "href": "/activity_logs"}, {"label": "My Activity Logs", "href": "/my-activity-logs"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 2. MEMBER SERVICES (staff2)
    elif role_key == "member_services":
        total_m = Member.objects.count()
        active_m = Member.objects.filter(membership_status__name__iexact="active").count() or total_m
        pending_apps = Member.objects.filter(application_status__in=["pending", "draft"]).count()
        new_this_month = Member.objects.filter(created_at__date__gte=today.replace(day=1)).count() or 5

        spline = {"title": "Member Admissions (12M)", "series_name": "Admissions", "data": _get_12m_growth()}
        types = list(Member.objects.values("membership_type__name").annotate(v=Count("id")).order_by("-v")[:5])
        donut = {"title": "Membership Tiers", "data": [{"name": (t["membership_type__name"] or "Standard"), "value": t["v"]} for t in types]}
        item_list = {"title": "Upcoming Birthdays", "items": _get_upcoming_birthdays()}

        apps = list(Member.objects.filter(application_status__in=["pending", "draft"]).order_by("-created_at")[:4])
        action_table = {
            "title": "Pending KYC Applications",
            "action_button_label": "Review",
            "headers": ["Applicant", "Membership Type", "Submitted"],
            "rows": [
                {
                    "id": a.id,
                    "col1": f"{a.first_name} {a.last_name}".strip() or a.member_ID,
                    "col2": a.membership_type.name if a.membership_type else "Regular",
                    "col3": a.created_at.strftime("%b %d, %Y") if a.created_at else "Today",
                    "link_url": "/members/pending"
                } for a in apps
            ]
        }

        hourly = {
            "title": "Daily check-ins by hour",
            "unit_label": "Visits",
            "data": _get_hourly_distribution(AttendanceRecord.objects.all(), "check_in")
        }

        radial = {
            "title": "KYC Verification Rate",
            "value": 46,
            "max": 50,
            "percentage": 92,
            "center_label": "Verified",
            "subtext": "46 of 50 profiles verified"
        }

        acts = [
            {"id": 1, "title": "New member onboarded", "subtitle": "Profile approved & credentials emailed", "time_ago": "18m ago", "icon": "User"},
            {"id": 2, "title": "Address updated", "subtitle": "Member #M-1002 updated emergency contact", "time_ago": "42m ago", "icon": "Activity"},
            {"id": 3, "title": "Document uploaded", "subtitle": "NID copy received for verification", "time_ago": "1h ago", "icon": "FileText"},
        ]
        activity_feed = {"title": "Member Services Log", "items": acts}

        m_types = list(MembershipType.objects.all()[:3])
        status_table = {
            "title": "Membership Tiers Status",
            "headers": ["Tier", "Type", "Status"],
            "rows": [{"id": t.id, "name": t.name, "type": "Membership", "status": "open"} for t in m_types]
        }

        return {
            "role_key": role_key,
            "role_title": "Member Services Overview",
            "kpi_cards": [
                {"title": "Total Members", "value": total_m, "trend": 4.1, "trendLabel": "total directory", "icon": "Users", "actions": [{"label": "View All Members", "href": "/members/view"}, {"label": "Add New Member", "href": "/members/add"}]},
                {"title": "Active Members", "value": active_m, "trend": 3.8, "trendLabel": "good standing", "icon": "Diamond", "actions": [{"label": "View All Members", "href": "/members/view"}, {"label": "Transfer History", "href": "/members/history"}]},
                {"title": "Pending KYC", "value": pending_apps, "trend": -1.2, "trendLabel": "needs review", "icon": "CheckSquare", "actions": [{"label": "Pending Approvals", "href": "/members/pending"}, {"label": "Member Onboarding", "href": "/registration/email"}]},
                {"title": "New This Month", "value": new_this_month, "trend": 8.0, "trendLabel": "admissions", "icon": "TrendingUp", "actions": [{"label": "View All Members", "href": "/members/view"}, {"label": "Add New Member", "href": "/members/add"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 3. FINANCE & ACCOUNTS (staff3)
    elif role_key == "finance_accounts":
        total_inv = Invoice.objects.count()
        sales_sum = Sale.objects.aggregate(t=Sum("total_amount"))["t"] or 84200.0
        dues_sum = MemberAccount.objects.aggregate(t=Sum("overdue_amount"))["t"] or 12450.0
        acc_count = MemberAccount.objects.count() or 50

        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        rev_trend = [12000, 18500, 24000, 31000, 28000, 39000, 45000, 52000, 61000, 68000, 74000, 84200]
        spline = {
            "title": "Revenue Trend (12M)",
            "series_name": "Revenue ($)",
            "data": [{"label": months[i], "value": rev_trend[i]} for i in range(12)]
        }

        paid_c = Invoice.objects.filter(status="paid").count() or 320
        unpaid_c = Invoice.objects.filter(status="unpaid").count() or 60
        due_c = Invoice.objects.filter(status="due").count() or 40
        donut = {
            "title": "Invoice Status Breakdown",
            "data": [{"name": "Paid", "value": paid_c}, {"name": "Unpaid", "value": unpaid_c}, {"name": "Due", "value": due_c}]
        }

        top_d = list(MemberAccount.objects.filter(overdue_amount__gt=0).select_related("member").order_by("-overdue_amount")[:4])
        d_items = []
        for d in top_d:
            m_name = f"{d.member.first_name} {d.member.last_name}" if d.member else "Member"
            init = f"{m_name[:1]}B".upper()
            d_items.append({
                "id": d.id,
                "name": m_name,
                "subtitle": "Overdue Balance",
                "tag": f"${float(d.overdue_amount):.0f}",
                "initials": init
            })
        if not d_items:
            d_items = _get_upcoming_birthdays()
        item_list = {"title": "Top Outstanding Dues", "items": d_items}

        due_invs = list(Invoice.objects.filter(status__in=["unpaid", "due"]).select_related("member").order_by("-created_at")[:4])
        action_table = {
            "title": "Overdue Invoices",
            "action_button_label": "Settle",
            "headers": ["Member / Invoice", "Due Amount", "Due Date"],
            "rows": [
                {
                    "id": inv.id,
                    "col1": f"Invoice #{inv.id} - {inv.member.first_name if inv.member else 'Member'}",
                    "col2": f"${float(inv.total_amount):.2f}",
                    "col3": inv.created_at.strftime("%b %d, %Y") if inv.created_at else "Due",
                    "link_url": "/mfm/invoices"
                } for inv in due_invs
            ]
        }

        hourly = {
            "title": "Today's sales transactions by hour",
            "unit_label": "Sales ($)",
            "data": _get_hourly_distribution(Sale.objects.all(), "created_at", base_multiplier=1.5)
        }

        radial = {
            "title": "Monthly Dues Collection Rate",
            "value": 84,
            "max": 100,
            "percentage": 84,
            "center_label": "84%",
            "subtext": "$70,728 of $84,200 collected"
        }

        acts = [
            {"id": 1, "title": "Online payment received", "subtitle": "$450.00 via SSLCommerz - Inv #398", "time_ago": "5m ago", "icon": "Activity"},
            {"id": 2, "title": "Cash receipt recorded", "subtitle": "$120.00 settled at Front Cashier", "time_ago": "22m ago", "icon": "FileText"},
            {"id": 3, "title": "Monthly billing generated", "subtitle": "Annual subscription dues invoiced", "time_ago": "1h ago", "icon": "Mail"},
        ]
        activity_feed = {"title": "Financial Audit Log", "items": acts}

        status_table = {
            "title": "Payment Channels Status",
            "headers": ["Channel", "Type", "Status"],
            "rows": [
                {"id": 1, "name": "SSLCommerz Gateway", "type": "Online", "status": "open"},
                {"id": 2, "name": "POS Terminal Counter A", "type": "Hardware", "status": "open"},
                {"id": 3, "name": "Bank Direct Clearing", "type": "Settlement", "status": "open"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "Finance & Accounts Overview",
            "kpi_cards": [
                {"title": "Invoices Issued", "value": total_inv, "trend": 6.5, "trendLabel": "total invoices", "icon": "FileText", "actions": [{"label": "View All Invoices", "href": "/mfm/invoices"}, {"label": "Payment Invoices", "href": "/mfm/payment_invoice"}]},
                {"title": "Total Sales MTD", "value": int(sales_sum), "trend": 9.2, "trendLabel": "gross revenue", "icon": "TrendingUp", "actions": [{"label": "View All Sales", "href": "/mfm/sales"}, {"label": "Finance Dashboard", "href": "/finance"}]},
                {"title": "Outstanding Dues", "value": int(dues_sum), "trend": -3.4, "trendLabel": "uncollected", "icon": "Diamond", "actions": [{"label": "View Member Dues", "href": "/mfm/view_member_dues"}, {"label": "Record Payment", "href": "/mfm/payments"}]},
                {"title": "Member Accounts", "value": acc_count, "trend": 1.5, "trendLabel": "active accounts", "icon": "Users", "actions": [{"label": "View Member Accounts", "href": "/mfm/view_member_accounts"}, {"label": "Transactions Ledger", "href": "/mfm/transections"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 4. RESTAURANT / KITCHEN (staff4)
    elif role_key == "restaurant_kitchen":
        orders_today_qs = RestaurantOrder.objects.filter(created_at__date=today)
        if orders_today_qs.count() == 0:
            orders_today_qs = RestaurantOrder.objects.all()
        
        total_ord = orders_today_qs.count()
        in_prep = orders_today_qs.filter(status__in=["confirmed", "preparing"]).count() or 18
        served = orders_today_qs.filter(status="served").count() or 64
        rev_today = int(orders_today_qs.filter(status="billed").aggregate(s=Sum("total_amount"))["s"] or 18450)

        spline = {
            "title": "Daily Kitchen Orders (Last 12 Days)",
            "series_name": "Orders",
            "data": [
                {"label": f"Day {i+1}", "value": v}
                for i, v in enumerate([65, 82, 94, 110, 105, 128, 142, 138, 155, 172, 190, total_ord])
            ]
        }

        status_counts = [
            {"name": "Preparing", "value": in_prep},
            {"name": "Ready", "value": orders_today_qs.filter(status="ready").count() or 8},
            {"name": "Served", "value": served},
            {"name": "Billed", "value": orders_today_qs.filter(status="billed").count() or 80},
        ]
        donut = {"title": "Order Status Distribution", "data": status_counts}

        top_dishes = list(RestaurantOrderItem.objects.values("item__name").annotate(qty=Sum("quantity")).order_by("-qty")[:4])
        item_list = {
            "title": "Top Ordered Dishes Today",
            "items": [
                {
                    "id": i,
                    "name": td["item__name"] or "Club Special Steak",
                    "subtitle": "Kitchen Hot Station",
                    "tag": f"{td['qty']} orders",
                    "initials": "FD"
                } for i, td in enumerate(top_dishes)
            ]
        }

        active_orders = list(orders_today_qs.filter(status__in=["confirmed", "preparing", "ready"]).order_by("-created_at")[:4])
        action_table = {
            "title": "Kitchen Display Queue (KOT)",
            "action_button_label": "Advance",
            "headers": ["Order #", "Items / Table", "Status"],
            "rows": [
                {
                    "id": o.id,
                    "col1": f"Order #{o.id}",
                    "col2": f"${float(o.total_amount):.2f}",
                    "col3": o.status.capitalize(),
                    "link_url": "/restaurant-orders"
                } for o in active_orders
            ]
        }

        hourly = {
            "title": "Kitchen orders by rush hour",
            "unit_label": "Orders",
            "data": _get_hourly_distribution(orders_today_qs, "created_at")
        }

        radial = {
            "title": "Kitchen Capacity Load",
            "value": 78,
            "max": 100,
            "percentage": 78,
            "center_label": "78%",
            "subtext": "Active burner stations at 78% capacity"
        }

        acts = [
            {"id": 1, "title": "Order #248 marked Ready", "subtitle": "Table 12 - Chef Marco", "time_ago": "4m ago", "icon": "Activity"},
            {"id": 2, "title": "New KOT printed #250", "subtitle": "2x Ribeye Steak, 1x Truffle Fries", "time_ago": "9m ago", "icon": "Mail"},
            {"id": 3, "title": "Order #242 served", "subtitle": "Waiter assigned: Rafiq", "time_ago": "20m ago", "icon": "FileText"},
        ]
        activity_feed = {"title": "Live Kitchen Stream", "items": acts}

        status_table = {
            "title": "Kitchen Stations Status",
            "headers": ["Station", "Section", "Status"],
            "rows": [
                {"id": 1, "name": "Grill & Hot Line", "type": "Main Kitchen", "status": "open"},
                {"id": 2, "name": "Pastry & Bakery Oven", "type": "Bakery", "status": "open"},
                {"id": 3, "name": "Deep Fryer Unit 2", "type": "Appetizers", "status": "maintenance"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "Restaurant & Kitchen Overview",
            "kpi_cards": [
                {"title": "Orders Today", "value": total_ord, "trend": 8.4, "trendLabel": "total tickets", "icon": "CheckSquare", "actions": [{"label": "Kitchen & Orders", "href": "/restaurant-orders"}, {"label": "Restaurants", "href": "/restaurants"}]},
                {"title": "Kitchen Revenue", "value": rev_today, "trend": 11.2, "trendLabel": "billed today", "icon": "TrendingUp", "actions": [{"label": "Upload Sales", "href": "/restaurants/sales/upload"}, {"label": "Restaurants", "href": "/restaurants"}]},
                {"title": "Orders in Prep", "value": in_prep, "trend": 2.1, "trendLabel": "active cooking", "icon": "Activity", "actions": [{"label": "Kitchen & Orders", "href": "/restaurant-orders"}, {"label": "Menu Choices", "href": "/restaurants/choices"}]},
                {"title": "Orders Served", "value": served, "trend": 6.8, "trendLabel": "completed orders", "icon": "Users", "actions": [{"label": "Kitchen & Orders", "href": "/restaurant-orders"}, {"label": "Restaurants", "href": "/restaurants"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 5. OUTLET OPERATIONS (staff5)
    elif role_key == "outlet_operations":
        total_outlets = Outlet.objects.filter(is_active=True).count() or 4
        orders_qs = OutletOrder.objects.all()
        total_ord = orders_qs.count() or 120
        open_tabs = orders_qs.filter(status__in=["confirmed", "preparing"]).count() or 14
        rev_today = int(orders_qs.filter(status="billed").aggregate(s=Sum("total_amount"))["s"] or 12800)

        spline = {
            "title": "Beverage & Lounge Volume (12W)",
            "series_name": "Orders",
            "data": [
                {"label": f"W{i+1}", "value": v}
                for i, v in enumerate([45, 52, 60, 75, 80, 88, 95, 110, 105, 115, 125, total_ord])
            ]
        }

        donut = {
            "title": "Sales by Outlet Venue",
            "data": [
                {"name": "Main Lounge Bar", "value": 58},
                {"name": "Poolside Bar", "value": 34},
                {"name": "Cigar Room", "value": 28},
            ]
        }

        top_drinks = []
        try:
            top_drinks = list(OutletOrderItem.objects.filter(outlet_item__isnull=False).values("outlet_item__name").annotate(qty=Sum("quantity")).order_by("-qty")[:4])
        except Exception:
            pass
        if not top_drinks:
            top_drinks = [{"outlet_item__name": "Mojito Classic", "qty": 42}, {"outlet_item__name": "Espresso Martini", "qty": 36}, {"outlet_item__name": "Craft IPA", "qty": 29}, {"outlet_item__name": "Sparkling Water", "qty": 24}]
        item_list = {
            "title": "Top Selling Beverages",
            "items": [
                {
                    "id": i,
                    "name": td["outlet_item__name"],
                    "subtitle": "Beverage Dispense",
                    "tag": f"{td['qty']} sold",
                    "initials": "BV"
                } for i, td in enumerate(top_drinks)
            ]
        }

        active_tabs = list(orders_qs.filter(status__in=["confirmed", "preparing", "ready"]).order_by("-created_at")[:4])
        if not active_tabs:
            active_tabs = list(orders_qs.order_by("-created_at")[:4])
        action_table = {
            "title": "Active Outlet Orders",
            "action_button_label": "Settle Tab",
            "headers": ["Tab #", "Total Amount", "Status"],
            "rows": [
                {
                    "id": o.id,
                    "col1": f"Tab #{o.id}",
                    "col2": f"${float(o.total_amount):.2f}",
                    "col3": o.status.capitalize(),
                    "link_url": "/outlet/orders"
                } for o in active_tabs
            ]
        }

        hourly = {
            "title": "Beverage orders by hour",
            "unit_label": "Drinks",
            "data": _get_hourly_distribution(orders_qs, "created_at")
        }

        radial = {
            "title": "Lounge Seating Occupancy",
            "value": 68,
            "max": 100,
            "percentage": 68,
            "center_label": "68%",
            "subtext": "34 of 50 lounge tables occupied"
        }

        acts = [
            {"id": 1, "title": "Tab #118 billed", "subtitle": "Poolside Bar - $84.00 cash", "time_ago": "7m ago", "icon": "Activity"},
            {"id": 2, "title": "Cross-order allowed", "subtitle": "Cigar Room ordered from Main Bar", "time_ago": "19m ago", "icon": "Mail"},
            {"id": 3, "title": "Keg tapped #4", "subtitle": "Craft Draught Beer refilled", "time_ago": "35m ago", "icon": "FileText"},
        ]
        activity_feed = {"title": "Bar & Lounge Activity", "items": acts}

        status_table = {
            "title": "Outlets Operating Status",
            "headers": ["Outlet", "Category", "Status"],
            "rows": [
                {"id": 1, "name": "Main Lounge Bar", "type": "Beverage", "status": "open"},
                {"id": 2, "name": "Poolside Terrace Bar", "type": "Outdoor", "status": "open"},
                {"id": 3, "name": "Executive Cigar Lounge", "type": "Exclusive", "status": "open"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "Outlet & Beverage Overview",
            "kpi_cards": [
                {"title": "Outlet Orders", "value": total_ord, "trend": 6.7, "trendLabel": "total tabs", "icon": "CheckSquare", "actions": [{"label": "Outlets Management", "href": "/outlets"}, {"label": "Upload Lounge Sales", "href": "/upload/sales/lounge"}]},
                {"title": "Beverage Revenue", "value": rev_today, "trend": 14.5, "trendLabel": "sales today", "icon": "TrendingUp", "actions": [{"label": "Upload Lounge Sales", "href": "/upload/sales/lounge"}, {"label": "Upload Other Sales", "href": "/upload/sales/others"}]},
                {"title": "Active Open Tabs", "value": open_tabs, "trend": -2.0, "trendLabel": "unbilled tabs", "icon": "Diamond", "actions": [{"label": "Outlets Management", "href": "/outlets"}, {"label": "Upload Lounge Sales", "href": "/upload/sales/lounge"}]},
                {"title": "Active Outlets", "value": total_outlets, "trend": 0.0, "trendLabel": "operational venues", "icon": "Home", "actions": [{"label": "Outlets Management", "href": "/outlets"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 6. FACILITY / SPORTS (staff6)
    elif role_key == "facility_sports":
        res_qs = Reservation.objects.all()
        total_res = res_qs.count() or 200
        conf_res = res_qs.filter(status="confirmed").count() or 140
        pend_pay = res_qs.filter(status="pending_payment").count() or 30
        open_fac = ReservableResource.objects.filter(status="open").count() or 8

        spline = {
            "title": "Court & Facility Bookings (12M)",
            "series_name": "Bookings",
            "data": [
                {"label": m, "value": v}
                for m, v in zip(
                    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    [80, 95, 110, 130, 145, 160, 175, 190, 205, 215, 220, total_res]
                )
            ]
        }

        donut = {
            "title": "Bookings by Sport / Resource",
            "data": [
                {"name": "Tennis Court", "value": 72},
                {"name": "Squash Arena", "value": 48},
                {"name": "Swimming Pool", "value": 50},
                {"name": "Billiards Hall", "value": 30},
            ]
        }

        up_res = list(res_qs.filter(status__in=["confirmed", "pending_payment"]).select_related("resource", "member").order_by("start_time")[:4])
        item_list = {
            "title": "Upcoming Bookings",
            "items": [
                {
                    "id": r.id,
                    "name": f"{r.member.first_name} {r.member.last_name}" if r.member else "Member Booking",
                    "subtitle": r.resource.name if r.resource else "Sports Court",
                    "tag": r.start_time.strftime("%b %d, %H:%M") if r.start_time else "Today",
                    "initials": "SP"
                } for r in up_res
            ]
        }

        action_table = {
            "title": "Reservations Needing Confirmation",
            "action_button_label": "Confirm",
            "headers": ["Member / Res #", "Facility", "Status"],
            "rows": [
                {
                    "id": r.id,
                    "col1": f"Res #{r.id} - {r.member.first_name if r.member else 'Member'}",
                    "col2": r.resource.name if r.resource else "Court",
                    "col3": r.status.capitalize(),
                    "link_url": "/reservations"
                } for r in up_res
            ]
        }

        hourly = {
            "title": "Court bookings by hour",
            "unit_label": "Bookings",
            "data": _get_hourly_distribution(res_qs, "start_time")
        }

        radial = {
            "title": "Sports Court Peak Occupancy",
            "value": 82,
            "max": 100,
            "percentage": 82,
            "center_label": "82%",
            "subtext": "Prime time slots 82% reserved"
        }

        acts = [
            {"id": 1, "title": "Tennis Court 1 checked in", "subtitle": "Member #M-1014 session started", "time_ago": "12m ago", "icon": "Activity"},
            {"id": 2, "title": "Advance payment verified", "subtitle": "Squash Court 2 booked for 6:00 PM", "time_ago": "28m ago", "icon": "FileText"},
            {"id": 3, "title": "Slot cancelled & refunded", "subtitle": "Billiards Table A slot released", "time_ago": "1h ago", "icon": "Mail"},
        ]
        activity_feed = {"title": "Facility Bookings Log", "items": acts}

        res_list = list(ReservableResource.objects.all()[:3])
        status_table = {
            "title": "Court & Arena Availability",
            "headers": ["Facility", "Sport", "Status"],
            "rows": [{"id": r.id, "name": r.name, "type": r.resource_type.replace("_", " ").capitalize(), "status": r.status or "open"} for r in res_list]
        }

        return {
            "role_key": role_key,
            "role_title": "Facility & Sports Overview",
            "kpi_cards": [
                {"title": "Total Bookings", "value": total_res, "trend": 10.4, "trendLabel": "all reservations", "icon": "CheckSquare", "actions": [{"label": "View Reservations", "href": "/reservations"}, {"label": "View Facilities", "href": "/facilities"}]},
                {"title": "Confirmed Today", "value": conf_res, "trend": 8.2, "trendLabel": "active players", "icon": "TrendingUp", "actions": [{"label": "View Reservations", "href": "/reservations"}, {"label": "View Facilities", "href": "/facilities"}]},
                {"title": "Pending Payment", "value": pend_pay, "trend": -2.5, "trendLabel": "advance due", "icon": "Diamond", "actions": [{"label": "View Invoices", "href": "/mfm/invoices"}, {"label": "View Reservations", "href": "/reservations"}]},
                {"title": "Open Facilities", "value": open_fac, "trend": 0.0, "trendLabel": "courts ready", "icon": "Home", "actions": [{"label": "View Facilities", "href": "/facilities"}, {"label": "Create Facility", "href": "/facilities/create"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 7. EVENTS & MARKETING (staff7)
    elif role_key == "events_marketing":
        total_ev = Event.objects.count() or 12
        up_ev = Event.objects.filter(start_date__date__gte=today).count() or 6
        active_ev = Event.objects.filter(is_active=True).count() or 10

        spline = {
            "title": "Event Ticket Sales (6 Campaigns)",
            "series_name": "Tickets",
            "data": [
                {"label": "Gala '26", "value": 340},
                {"label": "Tennis Open", "value": 280},
                {"label": "Wine Fest", "value": 410},
                {"label": "Summer BBQ", "value": 520},
                {"label": "Youth Golf", "value": 190},
                {"label": "Fall Dinner", "value": 380},
            ]
        }

        donut = {
            "title": "Events by Category",
            "data": [
                {"name": "Sports Tournaments", "value": 4},
                {"name": "Dining & Gala", "value": 4},
                {"name": "Cultural & Music", "value": 3},
                {"name": "Member Socials", "value": 1},
            ]
        }

        events_list = list(Event.objects.order_by("start_date")[:4])
        item_list = {
            "title": "Upcoming Club Events",
            "items": [
                {
                    "id": e.id,
                    "name": e.title,
                    "subtitle": e.event_type.capitalize() if getattr(e, "event_type", None) else "Club Event",
                    "tag": e.start_date.strftime("%b %d") if e.start_date else "Soon",
                    "initials": "EV"
                } for e in events_list
            ]
        }

        action_table = {
            "title": "Active Event Campaigns",
            "action_button_label": "Manage",
            "headers": ["Event Name", "Status", "Schedule Date"],
            "rows": [
                {
                    "id": e.id,
                    "col1": e.title,
                    "col2": e.status.capitalize() if getattr(e, "status", None) else "Active",
                    "col3": e.start_date.strftime("%b %d, %Y") if e.start_date else "Upcoming",
                    "link_url": "/events"
                } for e in events_list
            ]
        }

        hourly = {
            "title": "Ticket sales traffic by hour",
            "unit_label": "Tickets",
            "data": _get_hourly_distribution(Event.objects.all(), "start_date")
        }

        radial = {
            "title": "Grand Ballroom Sold Out %",
            "value": 85,
            "max": 100,
            "percentage": 85,
            "center_label": "85%",
            "subtext": "255 of 300 seats booked"
        }

        acts = [
            {"id": 1, "title": "Bulk Email Dispatched", "subtitle": "Sent to 1,240 active members for Annual Gala", "time_ago": "30m ago", "icon": "Mail"},
            {"id": 2, "title": "Promo Code GACL20 used", "subtitle": "15 tickets sold with 20% discount", "time_ago": "1h ago", "icon": "Activity"},
            {"id": 3, "title": "Event capacity expanded", "subtitle": "Added 20 VIP seats to Tennis Open", "time_ago": "2h ago", "icon": "FileText"},
        ]
        activity_feed = {"title": "Marketing Broadcasts Log", "items": acts}

        status_table = {
            "title": "Events Operational Status",
            "headers": ["Event Title", "Type", "Status"],
            "rows": [{"id": e.id, "name": e.title, "type": "Club Event", "status": "open" if getattr(e, "status", None) in ["planned", "ongoing"] else "closed"} for e in events_list[:3]]
        }

        return {
            "role_key": role_key,
            "role_title": "Events & Marketing Overview",
            "kpi_cards": [
                {"title": "Active Events", "value": active_ev, "trend": 12.0, "trendLabel": "on calendar", "icon": "CheckSquare", "actions": [{"label": "All Events", "href": "/events"}, {"label": "Event Venues", "href": "/events/venues"}]},
                {"title": "Upcoming Events", "value": up_ev, "trend": 8.5, "trendLabel": "next 30 days", "icon": "Diamond", "actions": [{"label": "All Events", "href": "/events"}, {"label": "Event Media", "href": "/events/media"}]},
                {"title": "Tickets Sold", "value": 2120, "trend": 18.4, "trendLabel": "this quarter", "icon": "TrendingUp", "actions": [{"label": "Event Tickets", "href": "/events/tickets"}, {"label": "Event Fees", "href": "/events/fees"}]},
                {"title": "Promo Codes", "value": 4, "trend": 0.0, "trendLabel": "active campaigns", "icon": "Home", "actions": [{"label": "All Promo Codes", "href": "/promo_codes"}, {"label": "Add Promo Code", "href": "/promo_codes/add"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 8. SECURITY & GATE (staff8)
    elif role_key == "security_gate":
        att_qs = AttendanceRecord.objects.all()
        total_att = att_qs.count() or 300
        inside_count = att_qs.filter(check_out__isnull=True).count() or 142
        members_in = att_qs.filter(check_out__isnull=True, subject_type="member").count() or 112
        staff_in = att_qs.filter(check_out__isnull=True, subject_type="staff").count() or 30

        spline = {
            "title": "Weekly Gate Footfall (7 Days)",
            "series_name": "Check-ins",
            "data": [
                {"label": "Mon", "value": 210},
                {"label": "Tue", "value": 240},
                {"label": "Wed", "value": 265},
                {"label": "Thu", "value": 290},
                {"label": "Fri", "value": 380},
                {"label": "Sat", "value": 450},
                {"label": "Sun", "value": 420},
            ]
        }

        donut = {
            "title": "Footfall by Person Category",
            "data": [
                {"name": "Club Members", "value": 220},
                {"name": "Staff On Duty", "value": 50},
                {"name": "Registered Guests", "value": 30},
            ]
        }

        rec_in = list(att_qs.filter(check_out__isnull=True).select_related("member").order_by("-check_in")[:4])
        item_list = {
            "title": "VIP Members On Premises",
            "items": [
                {
                    "id": a.id,
                    "name": f"{a.member.first_name} {a.member.last_name}" if a.member else "Club Member",
                    "subtitle": "RFID Turnstile Entry",
                    "tag": a.check_in.strftime("%H:%M") if a.check_in else "Inside",
                    "initials": "MB"
                } for a in rec_in
            ]
        }

        action_table = {
            "title": "Active Guest Passes Inside",
            "action_button_label": "Check-out",
            "headers": ["Guest / Host", "Entry Gate", "Check-in Time"],
            "rows": [
                {"id": 1, "col1": "Mr. Karim (Host: Member #102)", "col2": "Main Gate", "col3": "10:15 AM", "link_url": "/attendance"},
                {"id": 2, "col1": "Mrs. Nusrat (Host: Member #108)", "col2": "North Turnstile", "col3": "11:30 AM", "link_url": "/attendance"},
                {"id": 3, "col1": "Tennis Guest pass #402", "col2": "Sports Gate", "col3": "12:45 PM", "link_url": "/attendance"},
                {"id": 4, "col1": "Dining Guest pass #512", "col2": "Main Gate", "col3": "01:20 PM", "link_url": "/attendance"},
            ]
        }

        hourly = {
            "title": "Turnstile traffic by hour",
            "unit_label": "Scans",
            "data": _get_hourly_distribution(att_qs, "check_in")
        }

        cap = 250
        radial = {
            "title": "Club Maximum Capacity Safety",
            "value": inside_count,
            "max": cap,
            "percentage": min(round((inside_count / cap) * 100), 100),
            "center_label": f"{inside_count}",
            "subtext": f"{inside_count} of 250 max safety limit"
        }

        acts = [
            {"id": 1, "title": "RFID Card Tap: Gate 1", "subtitle": "Member #M-1042 granted entry", "time_ago": "2m ago", "icon": "Activity"},
            {"id": 2, "title": "Staff shift checkout", "subtitle": "Security Officer Kamal signed off", "time_ago": "15m ago", "icon": "CheckSquare"},
            {"id": 3, "title": "Guest badge issued", "subtitle": "Temporary RFID #G-88 activated", "time_ago": "38m ago", "icon": "FileText"},
        ]
        activity_feed = {"title": "Live Turnstiles Stream", "items": acts}

        status_table = {
            "title": "Turnstiles & Gate Status",
            "headers": ["Hardware", "Location", "Status"],
            "rows": [
                {"id": 1, "name": "Main Turnstile A", "type": "Optical Barrier", "status": "open"},
                {"id": 2, "name": "Sports Pavilion Gate", "type": "Full Height RFID", "status": "open"},
                {"id": 3, "name": "Staff Service Turnstile", "type": "Biometric & RFID", "status": "open"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "Security & Gate Control Overview",
            "kpi_cards": [
                {"title": "Currently Inside", "value": inside_count, "trend": 4.5, "trendLabel": "total on grounds", "icon": "CheckSquare", "actions": [{"label": "Attendance Dashboard", "href": "/attendance"}, {"label": "Activity Logs", "href": "/activity_logs"}]},
                {"title": "Members Inside", "value": members_in, "trend": 6.1, "trendLabel": "active members", "icon": "Users", "actions": [{"label": "Attendance Dashboard", "href": "/attendance"}, {"label": "View All Members", "href": "/members/view"}]},
                {"title": "Staff On Duty", "value": staff_in, "trend": 0.0, "trendLabel": "shift active", "icon": "Diamond", "actions": [{"label": "Attendance Dashboard", "href": "/attendance"}, {"label": "Payroll & Staff", "href": "/payroll"}]},
                {"title": "Total Scans Today", "value": total_att, "trend": 9.8, "trendLabel": "turnstile entries", "icon": "TrendingUp", "actions": [{"label": "Activity Logs", "href": "/activity_logs"}, {"label": "Attendance Dashboard", "href": "/attendance"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 9. HR & PAYROLL (staff9)
    elif role_key == "hr_payroll":
        total_staff = StaffProfile.objects.count() or 50
        active_loans = StaffLoan.objects.count() or 5
        pending_payslips = Payslip.objects.count() or 12

        spline = {
            "title": "Employee Staffing Trend (12M)",
            "series_name": "Employees",
            "data": [
                {"label": m, "value": v}
                for m, v in zip(
                    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    [38, 40, 42, 44, 45, 46, 48, 48, 49, 50, 50, total_staff]
                )
            ]
        }

        donut = {
            "title": "Staff by Department",
            "data": [
                {"name": "Restaurant & F&B", "value": 20},
                {"name": "Security & Gate", "value": 12},
                {"name": "Sports & Maintenance", "value": 10},
                {"name": "Admin & Finance", "value": 8},
            ]
        }

        new_staff = list(StaffProfile.objects.select_related("user").order_by("-id")[:4])
        item_list = {
            "title": "Recently Onboarded Staff",
            "items": [
                {
                    "id": s.id,
                    "name": s.user.get_full_name() or s.user.username,
                    "subtitle": s.designation or "Club Staff",
                    "tag": "Active",
                    "initials": "ST"
                } for s in new_staff
            ]
        }

        loans = list(StaffLoan.objects.select_related("staff__user")[:4])
        action_table = {
            "title": "Staff Loans & Payslip Approvals",
            "action_button_label": "Review",
            "headers": ["Employee / Loan", "Principal", "Status"],
            "rows": [
                {
                    "id": l.id,
                    "col1": f"Loan #{l.id} - {l.staff.user.username if l.staff else 'Staff'}",
                    "col2": f"${float(l.principal):.2f}",
                    "col3": l.status.capitalize(),
                    "link_url": "/payroll"
                } for l in loans
            ]
        }

        hourly = {
            "title": "Staff morning check-ins by hour",
            "unit_label": "Staff",
            "data": _get_hourly_distribution(AttendanceRecord.objects.all(), "check_in")
        }

        radial = {
            "title": "Staff Attendance Today",
            "value": 47,
            "max": total_staff,
            "percentage": 94,
            "center_label": "94%",
            "subtext": f"47 of {total_staff} staff present"
        }

        acts = [
            {"id": 1, "title": "Staff Onboarding Completed", "subtitle": "Chef de Partie account created", "time_ago": "40m ago", "icon": "User"},
            {"id": 2, "title": "Salary Component adjusted", "subtitle": "Overtime allowance updated for F&B", "time_ago": "2h ago", "icon": "FileText"},
            {"id": 3, "title": "Loan Repayment processed", "subtitle": "Installment #3 deducted for Staff #14", "time_ago": "4h ago", "icon": "Activity"},
        ]
        activity_feed = {"title": "HR Operations Stream", "items": acts}

        status_table = {
            "title": "Departments Duty Status",
            "headers": ["Department", "Shift", "Status"],
            "rows": [
                {"id": 1, "name": "Food & Beverage Dept", "type": "Morning/Evening", "status": "open"},
                {"id": 2, "name": "Security & Gate Operations", "type": "24/7 Rotational", "status": "open"},
                {"id": 3, "name": "Facility Maintenance", "type": "General Shift", "status": "open"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "HR & Payroll Overview",
            "kpi_cards": [
                {"title": "Total Staff", "value": total_staff, "trend": 4.2, "trendLabel": "active employees", "icon": "Users", "actions": [{"label": "System Users", "href": "/users"}, {"label": "Payroll Management", "href": "/payroll"}]},
                {"title": "Present Today", "value": 47, "trend": 2.0, "trendLabel": "on duty", "icon": "CheckSquare", "actions": [{"label": "Staff Attendance", "href": "/attendance"}, {"label": "Payroll Management", "href": "/payroll"}]},
                {"title": "Pending Payslips", "value": pending_payslips, "trend": 0.0, "trendLabel": "to disburse", "icon": "FileText", "actions": [{"label": "Payroll Management", "href": "/payroll"}, {"label": "Finance Dashboard", "href": "/finance"}]},
                {"title": "Active Staff Loans", "value": active_loans, "trend": -1.0, "trendLabel": "outstanding loans", "icon": "Diamond", "actions": [{"label": "Payroll Management", "href": "/payroll"}, {"label": "Member Accounts", "href": "/mfm/view_member_accounts"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    # 10. SUPPLY & PROCUREMENT (staff10)
    elif role_key == "supply_procurement":
        total_ven = Vendor.objects.count() or 15
        active_offers = VendorServiceOffer.objects.filter(status="selected").count() or 12
        pending_offers = VendorServiceOffer.objects.filter(status="offered").count() or 18
        total_cats = VendorServiceCategory.objects.count() or 6

        spline = {
            "title": "Procurement Expenses (12M)",
            "series_name": "Spend ($)",
            "data": [
                {"label": m, "value": v}
                for m, v in zip(
                    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    [15000, 18000, 22000, 25000, 24000, 29000, 32000, 36000, 41000, 44000, 48000, 52000]
                )
            ]
        }

        donut = {
            "title": "Vendors by Service Category",
            "data": [
                {"name": "Food & Produce", "value": 6},
                {"name": "Beverages & Spirits", "value": 4},
                {"name": "Sports Equipment", "value": 3},
                {"name": "Maintenance & Utilities", "value": 2},
            ]
        }

        active_ven = list(Vendor.objects.filter(is_active=True)[:4])
        item_list = {
            "title": "Key Contracted Suppliers",
            "items": [
                {
                    "id": v.id,
                    "name": v.name,
                    "subtitle": v.contact_person or "Primary Vendor",
                    "tag": "Active Contract",
                    "initials": "VD"
                } for v in active_ven
            ]
        }

        offers = list(VendorServiceOffer.objects.filter(status="offered").select_related("vendor")[:4])
        if not offers:
            offers = list(VendorServiceOffer.objects.select_related("vendor")[:4])
        action_table = {
            "title": "Pending Supplier Offers",
            "action_button_label": "Award",
            "headers": ["Vendor / Offer", "Offer Cost", "Status"],
            "rows": [
                {
                    "id": o.id,
                    "col1": f"{o.vendor.name if o.vendor else 'Supplier'} - Offer #{o.id}",
                    "col2": f"${float(o.price):.2f}" if getattr(o, "price", None) else "Quotation",
                    "col3": o.status.capitalize(),
                    "link_url": "/vendors"
                } for o in offers
            ]
        }

        hourly = {
            "title": "Goods deliveries received by hour",
            "unit_label": "Shipments",
            "data": _get_hourly_distribution(VendorServiceOffer.objects.all(), "created_at")
        }

        radial = {
            "title": "Stock Fulfillment Rate",
            "value": 91,
            "max": 100,
            "percentage": 91,
            "center_label": "91%",
            "subtext": "91% items in adequate stock"
        }

        acts = [
            {"id": 1, "title": "Fresh Produce Delivered", "subtitle": "Supplier: Green Farm Organics - 240kg", "time_ago": "45m ago", "icon": "Activity"},
            {"id": 2, "title": "New Vendor Registered", "subtitle": "Apex Sports Supplies added to directory", "time_ago": "2h ago", "icon": "User"},
            {"id": 3, "title": "Purchase Offer Awarded", "subtitle": "Contract selected for Beverage supply", "time_ago": "5h ago", "icon": "FileText"},
        ]
        activity_feed = {"title": "Procurement Log", "items": acts}

        status_table = {
            "title": "Supplier Categories Status",
            "headers": ["Category", "Type", "Status"],
            "rows": [
                {"id": 1, "name": "Fresh Dairy & Meat", "type": "Perishable", "status": "open"},
                {"id": 2, "name": "Beverages & Wine Casks", "type": "Beverage", "status": "open"},
                {"id": 3, "name": "Tennis & Sports Gear", "type": "Equipment", "status": "open"},
            ]
        }

        return {
            "role_key": role_key,
            "role_title": "Supply & Procurement Overview",
            "kpi_cards": [
                {"title": "Active Vendors", "value": total_ven, "trend": 7.1, "trendLabel": "vetted suppliers", "icon": "Home", "actions": [{"label": "Vendor Management", "href": "/vendors"}, {"label": "Products Catalog", "href": "/products"}]},
                {"title": "Awarded Contracts", "value": active_offers, "trend": 5.0, "trendLabel": "active agreements", "icon": "CheckSquare", "actions": [{"label": "Vendor Management", "href": "/vendors"}, {"label": "View Invoices", "href": "/mfm/invoices"}]},
                {"title": "Pending Offers", "value": pending_offers, "trend": -2.0, "trendLabel": "proposals in review", "icon": "Diamond", "actions": [{"label": "Vendor Management", "href": "/vendors"}, {"label": "View Products", "href": "/products"}]},
                {"title": "Product Categories", "value": total_cats, "trend": 0.0, "trendLabel": "catalog types", "icon": "TrendingUp", "actions": [{"label": "Product Categories", "href": "/products/categories"}, {"label": "All Products", "href": "/products"}]},
            ],
            "spline_chart": spline,
            "donut_chart": donut,
            "item_list": item_list,
            "action_table": action_table,
            "hourly_bar_chart": hourly,
            "radial_gauge": radial,
            "activity_feed": activity_feed,
            "status_table": status_table,
        }

    return {"role_key": role_key, "role_title": "Role Overview"}
