from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from account.models import PermissonModel, GroupModel, AssignGroupPermission


class Command(BaseCommand):
    help = 'Creates initial admin and other model data'

    def handle(self, *args, **kwargs):
        self.create_admin_with_groups()

    def create_admin_with_groups(self):
        try:
            User = get_user_model()
            if not User.objects.filter(username="admin").exists():
                user = User.objects.create_superuser(
                    username="admin",
                    email="admin@example123.com",
                    password="admin"
                )
            else:
                user = User.objects.get(username="admin")
            all_permission_name = [
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
            permissions = []
            for permission_name in all_permission_name:
                permission, _ = PermissonModel.objects.get_or_create(name=permission_name)
                permissions.append(permission)

            group, _ = GroupModel.objects.get_or_create(name="super_admin")
            group.permission.set(permissions)

            if not AssignGroupPermission.objects.filter(user=user, group=group).exists():
                assigned_group = AssignGroupPermission.objects.create(
                    user=user)
                assigned_group.group.add(group)
                assigned_group.save()

            self.stdout.write(self.style.SUCCESS(
                "Admin user created with super admin group."))
        except Exception as e:
            self.stdout.write(
                "something went wrong", str(e))
