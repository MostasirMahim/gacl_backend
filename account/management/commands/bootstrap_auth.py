from django.core.management.base import BaseCommand
from django.db import transaction
from account.models import PermissonModel, GroupModel

ALL_PERMISSIONS = [
    # Main section permissions
    "employee_onboarding", "group_permission_management", "activity_log_management",
    "restaurant_management", "member_financial_management", "member_management",
    "promo_code_management", "event_management", "product_management",
    "facility_management", "view_all_users", "bulk_emails_management",
    "vendor_management", "payroll_management", "reservation_management",
    "outlet_management", "attendance_management",
    # Granular action sub-permissions
    "member:view", "member:create", "member:edit", "member:delete", "member:export",
    "member_financial:view_invoices", "member_financial:generate_invoice", "member_financial:process_payment", "member_financial:adjust_dues",
    "restaurant:view_menu", "restaurant:menu_edit", "restaurant:order_create", "restaurant:kitchen_update", "restaurant:billing",
    "outlet:view_menu", "outlet:menu_edit", "outlet:order_create", "outlet:billing", "outlet:cross_order_rule",
    "reservation:view", "reservation:create", "reservation:cancel", "reservation:process_advance",
    "facility:view", "facility:create", "facility:edit", "facility:toggle_status",
    "event:view", "event:create", "event:edit", "event:delete", "event:manage_expenses",
    "attendance:view_records", "attendance:check_in_out", "attendance:card_issue", "attendance:guest_register",
    "payroll:view_structures", "payroll:edit_structure", "payroll:run_generate", "payroll:pay_slip", "payroll:manage_loans",
    "vendor:view", "vendor:create", "vendor:select_offer", "vendor:record_payment",
    "activity_log:view", "activity_log:export", "activity_log:clear",
    "group:view", "group:create", "group:edit", "group:delete", "group:assign_user",
    "employee:onboard", "employee:deactivate", "employee:edit_profile",
    "user:view_list", "user:view_detail", "user:reset_password",
    "email:view_logs", "email:send_single", "email:send_bulk", "email:template_edit",
    "product:view", "product:create", "product:edit", "product:adjust_stock",
    "promo_code:view", "promo_code:create", "promo_code:toggle_status"
]

CORE_GROUPS = [
    {
        "name": "super_admin",
        "permissions": ALL_PERMISSIONS
    },
    {
        "name": "club_member",
        "permissions": [
            "member_management", "restaurant_management", "outlet_management",
            "reservation_management", "event_management", "member_financial_management", "activity_log_management",
            "member:view", "member_financial:view_invoices", "member_financial:process_payment",
            "restaurant:view_menu", "restaurant:order_create",
            "outlet:view_menu", "outlet:order_create",
            "reservation:view", "reservation:create",
            "event:view", "activity_log:view"
        ]
    },
    {
        "name": "executive_admin",
        "permissions": ALL_PERMISSIONS
    },
    {
        "name": "member_services",
        "permissions": [
            "member_management", "view_all_users", "bulk_emails_management", "activity_log_management",
            "member:view", "member:create", "member:edit", "member:export",
            "user:view_list", "user:view_detail", "email:send_single", "activity_log:view"
        ]
    },
    {
        "name": "finance_accounts",
        "permissions": [
            "member_financial_management", "payroll_management", "vendor_management", "promo_code_management",
            "member_financial:view_invoices", "member_financial:generate_invoice", "member_financial:process_payment", "member_financial:adjust_dues",
            "payroll:view_structures", "payroll:edit_structure", "payroll:run_generate", "payroll:pay_slip", "payroll:manage_loans",
            "vendor:view", "vendor:record_payment", "promo_code:view", "promo_code:create"
        ]
    },
    {
        "name": "restaurant_kitchen",
        "permissions": [
            "restaurant_management", "product_management",
            "restaurant:view_menu", "restaurant:menu_edit", "restaurant:order_create", "restaurant:kitchen_update", "restaurant:billing",
            "product:view"
        ]
    },
    {
        "name": "outlet_operations",
        "permissions": [
            "outlet_management", "product_management",
            "outlet:view_menu", "outlet:menu_edit", "outlet:order_create", "outlet:billing", "outlet:cross_order_rule",
            "product:view"
        ]
    },
    {
        "name": "facility_sports",
        "permissions": [
            "reservation_management", "facility_management",
            "reservation:view", "reservation:create", "reservation:cancel", "reservation:process_advance",
            "facility:view", "facility:edit", "facility:toggle_status"
        ]
    },
    {
        "name": "events_marketing",
        "permissions": [
            "event_management", "promo_code_management", "bulk_emails_management",
            "event:view", "event:create", "event:edit", "event:manage_expenses",
            "promo_code:view", "promo_code:create", "email:send_bulk"
        ]
    },
    {
        "name": "security_gate",
        "permissions": [
            "attendance_management",
            "attendance:view_records", "attendance:check_in_out", "attendance:card_issue", "attendance:guest_register"
        ]
    },
    {
        "name": "hr_payroll",
        "permissions": [
            "employee_onboarding", "group_permission_management", "payroll_management", "attendance_management",
            "employee:onboard", "employee:deactivate", "employee:edit_profile",
            "group:view", "group:assign_user", "payroll:view_structures", "attendance:view_records"
        ]
    },
    {
        "name": "supply_procurement",
        "permissions": [
            "vendor_management", "product_management",
            "vendor:view", "vendor:create", "vendor:select_offer",
            "product:view", "product:create", "product:adjust_stock"
        ]
    }
]


class Command(BaseCommand):
    help = "Seeds all permissions and core authorization groups safely without assigning users."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting authorization permissions and groups bootstrap...")
        with transaction.atomic():
            # 1. Seed all permissions
            perm_obj_map = {}
            for p_name in ALL_PERMISSIONS:
                p_obj, _ = PermissonModel.objects.get_or_create(name=p_name)
                perm_obj_map[p_name] = p_obj
            self.stdout.write(self.style.SUCCESS(f"Seeded {len(perm_obj_map)} permissions."))

            # 2. Seed core groups and bind permissions
            for group_info in CORE_GROUPS:
                g_name = group_info["name"]
                g_obj, _ = GroupModel.objects.get_or_create(name=g_name)
                assigned_perms = [perm_obj_map[p] for p in group_info["permissions"] if p in perm_obj_map]
                g_obj.permission.set(assigned_perms)
                self.stdout.write(self.style.SUCCESS(f"Group '{g_name}' configured with {len(assigned_perms)} permissions."))

        self.stdout.write(self.style.SUCCESS("Successfully bootstrapped authorization infrastructure."))
