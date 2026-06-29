import re

"""
Centralized backend API URL path registry mapping inner request paths / sub-paths
to exact required granular action sub-permissions.
"""

PROTECTED_API_URLS = [
    # Attendance endpoints
    (re.compile(r"^/api/attendance/v1/attendance/scan/"), "attendance:check_in_out"),
    (re.compile(r"^/api/attendance/v1/attendance/records/"), "attendance:view_records"),
    (re.compile(r"^/api/attendance/v1/attendance/rfid-cards/"), "attendance:card_issue"),
    (re.compile(r"^/api/attendance/v1/attendance/guests/"), "attendance:guest_register"),
    (re.compile(r"^/api/attendance/v1/attendance/staff/"), "attendance:card_issue"),

    # Restaurant endpoints
    (re.compile(r"^/api/restaurant/v1/restaurants/kitchen/orders/"), "restaurant:kitchen_update"),
    (re.compile(r"^/api/restaurant/v1/restaurants/orders/\d+/bill/"), "restaurant:billing"),
    (re.compile(r"^/api/restaurant/v1/restaurants/orders/"), "restaurant:order_create"),
    (re.compile(r"^/api/restaurant/v1/restaurants/upload/excel"), "restaurant:menu_edit"),
    (re.compile(r"^/api/restaurant/v1/restaurants/items/"), "restaurant:menu_edit"),
    (re.compile(r"^/api/restaurant/v1/restaurants/"), "restaurant:view_menu"),

    # Outlet endpoints
    (re.compile(r"^/api/outlet/v1/outlets/cross-ordering-rules/"), "outlet:cross_order_rule"),
    (re.compile(r"^/api/outlet/v1/outlets/kitchen/orders/"), "outlet:order_create"),
    (re.compile(r"^/api/outlet/v1/outlets/orders/\d+/bill/"), "outlet:billing"),
    (re.compile(r"^/api/outlet/v1/outlets/orders/"), "outlet:order_create"),
    (re.compile(r"^/api/outlet/v1/outlets/items/"), "outlet:menu_edit"),
    (re.compile(r"^/api/outlet/v1/outlets/"), "outlet:view_menu"),

    # Reservation endpoints
    (re.compile(r"^/api/reservation/v1/reservations/\d+/pay-advance/"), "reservation:process_advance"),
    (re.compile(r"^/api/reservation/v1/reservations/\d+/cancel/"), "reservation:cancel"),
    (re.compile(r"^/api/reservation/v1/reservations/resources/"), "reservation:create"),
    (re.compile(r"^/api/reservation/v1/reservations/"), "reservation:view"),

    # Vendor endpoints
    (re.compile(r"^/api/vendor/v1/vendors/offers/\d+/select/"), "vendor:select_offer"),
    (re.compile(r"^/api/vendor/v1/vendors/offers/\d+/pay/"), "vendor:record_payment"),
    (re.compile(r"^/api/vendor/v1/vendors/offers/"), "vendor:view"),
    (re.compile(r"^/api/vendor/v1/vendors/"), "vendor:create"),

    # Payroll endpoints
    (re.compile(r"^/api/payroll/v1/payroll/runs/generate/"), "payroll:run_generate"),
    (re.compile(r"^/api/payroll/v1/payroll/slips/\d+/pay/"), "payroll:pay_slip"),
    (re.compile(r"^/api/payroll/v1/payroll/structures/"), "payroll:edit_structure"),
    (re.compile(r"^/api/payroll/v1/payroll/components/"), "payroll:edit_structure"),
    (re.compile(r"^/api/payroll/v1/payroll/"), "payroll:view_structures"),

    # Event endpoints
    (re.compile(r"^/api/event/v1/events/expenses/"), "event:manage_expenses"),
    (re.compile(r"^/api/event/v1/events/"), "event:view"),

    # Member endpoints
    (re.compile(r"^/api/member/v1/members/"), "member:view"),
]

def get_required_permission_for_path(path: str) -> str | None:
    for pattern, perm in PROTECTED_API_URLS:
        if pattern.search(path):
            return perm
    return None
