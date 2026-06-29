import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from account.models import PermissonModel, GroupModel, AssignGroupPermission
from attendance.models import StaffProfile

User = get_user_model()

SECTION_GROUPS = [
    {
        "group_name": "executive_admin",
        "description": "Executive Management / Super Admin Group",
        "permissions": [
            "employee_onboarding", "group_permission_management", "activity_log_management",
            "restaurant_management", "member_financial_management", "member_management", 
            "promo_code_management", "event_management", "product_management", 
            "facility_management", "view_all_users", "bulk_emails_management",
            "vendor_management", "payroll_management", "reservation_management",
            "outlet_management", "attendance_management",
            # Granular sub-permissions
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
        ],
        "staff": [
            {"username": "exec_manager", "email": "exec@gacl.test", "first_name": "Rahim", "last_name": "Chowdhury", "designation": "General Manager"}
        ]
    },
    {
        "group_name": "member_services",
        "description": "Member Relations & Reception",
        "permissions": [
            "member_management", "view_all_users", "bulk_emails_management", "activity_log_management",
            "member:view", "member:create", "member:edit", "member:export",
            "user:view_list", "user:view_detail", "email:send_single", "activity_log:view"
        ],
        "staff": [
            {"username": "member_mgr", "email": "member_mgr@gacl.test", "first_name": "Sadia", "last_name": "Islam", "designation": "Member Relations Manager"},
            {"username": "receptionist1", "email": "receptionist1@gacl.test", "first_name": "Nadia", "last_name": "Akter", "designation": "Receptionist"}
        ]
    },
    {
        "group_name": "finance_accounts",
        "description": "Finance, Billing & Payroll Accounting",
        "permissions": [
            "member_financial_management", "payroll_management", "vendor_management", "promo_code_management",
            "member_financial:view_invoices", "member_financial:generate_invoice", "member_financial:process_payment", "member_financial:adjust_dues",
            "payroll:view_structures", "payroll:edit_structure", "payroll:run_generate", "payroll:pay_slip", "payroll:manage_loans",
            "vendor:view", "vendor:record_payment", "promo_code:view", "promo_code:create"
        ],
        "staff": [
            {"username": "accountant1", "email": "accountant1@gacl.test", "first_name": "Tanvir", "last_name": "Haque", "designation": "Chief Accountant"},
            {"username": "billing_officer", "email": "billing@gacl.test", "first_name": "Fahim", "last_name": "Ahmed", "designation": "Billing Officer"}
        ]
    },
    {
        "group_name": "restaurant_kitchen",
        "description": "Restaurant Operations & Kitchen Staff",
        "permissions": [
            "restaurant_management", "product_management",
            "restaurant:view_menu", "restaurant:menu_edit", "restaurant:order_create", "restaurant:kitchen_update", "restaurant:billing",
            "product:view"
        ],
        "staff": [
            {"username": "head_chef", "email": "chef@gacl.test", "first_name": "Karim", "last_name": "Hossain", "designation": "Head Chef"},
            {"username": "rest_mgr", "email": "rest_mgr@gacl.test", "first_name": "Imran", "last_name": "Khan", "designation": "Restaurant Manager"},
            {"username": "waiter1", "email": "waiter1@gacl.test", "first_name": "Sabbir", "last_name": "Rahman", "designation": "Senior Waiter"}
        ]
    },
    {
        "group_name": "outlet_operations",
        "description": "Outlets - Sky Bar, Tea Lounge & Cigar Room",
        "permissions": [
            "outlet_management", "product_management",
            "outlet:view_menu", "outlet:menu_edit", "outlet:order_create", "outlet:billing", "outlet:cross_order_rule",
            "product:view"
        ],
        "staff": [
            {"username": "bar_mgr", "email": "bar_mgr@gacl.test", "first_name": "Tanvir", "last_name": "Bhuiyan", "designation": "Bar Manager"},
            {"username": "bar_attendant", "email": "bar_attendant@gacl.test", "first_name": "Jihan", "last_name": "Uddin", "designation": "Tea Lounge Attendant"}
        ]
    },
    {
        "group_name": "facility_sports",
        "description": "Sports Facilities & Room Bookings Desk",
        "permissions": [
            "reservation_management", "facility_management",
            "reservation:view", "reservation:create", "reservation:cancel", "reservation:process_advance",
            "facility:view", "facility:edit", "facility:toggle_status"
        ],
        "staff": [
            {"username": "sports_sup", "email": "sports@gacl.test", "first_name": "Mitu", "last_name": "Hossain", "designation": "Sports Supervisor"},
            {"username": "facility_coord", "email": "facility@gacl.test", "first_name": "Rafi", "last_name": "Islam", "designation": "Facility Coordinator"}
        ]
    },
    {
        "group_name": "events_marketing",
        "description": "Club Events, Promotions & Marketing",
        "permissions": [
            "event_management", "promo_code_management", "bulk_emails_management",
            "event:view", "event:create", "event:edit", "event:manage_expenses",
            "promo_code:view", "promo_code:create", "email:send_bulk"
        ],
        "staff": [
            {"username": "event_coord", "email": "events@gacl.test", "first_name": "Rumana", "last_name": "Akter", "designation": "Event Coordinator"},
            {"username": "mktg_exec", "email": "mktg@gacl.test", "first_name": "Shovon", "last_name": "Chowdhury", "designation": "Marketing Executive"}
        ]
    },
    {
        "group_name": "security_gate",
        "description": "Gate Attendance & Security Operations",
        "permissions": [
            "attendance_management",
            "attendance:view_records", "attendance:check_in_out", "attendance:card_issue", "attendance:guest_register"
        ],
        "staff": [
            {"username": "security_sup", "email": "security@gacl.test", "first_name": "Mahin", "last_name": "Khan", "designation": "Security Supervisor"},
            {"username": "gate_officer", "email": "gate@gacl.test", "first_name": "Hasan", "last_name": "Uddin", "designation": "Gate Officer"}
        ]
    },
    {
        "group_name": "hr_payroll",
        "description": "Human Resources & Employee Onboarding",
        "permissions": [
            "employee_onboarding", "group_permission_management", "payroll_management", "attendance_management",
            "employee:onboard", "employee:deactivate", "employee:edit_profile",
            "group:view", "group:assign_user", "payroll:view_structures", "attendance:view_records"
        ],
        "staff": [
            {"username": "hr_mgr", "email": "hr@gacl.test", "first_name": "Nusrat", "last_name": "Jahan", "designation": "HR Manager"},
            {"username": "hr_officer", "email": "hr_officer@gacl.test", "first_name": "Tania", "last_name": "Rahman", "designation": "HR Officer"}
        ]
    },
    {
        "group_name": "supply_procurement",
        "description": "Vendor Management & Supply Procurement",
        "permissions": [
            "vendor_management", "product_management",
            "vendor:view", "vendor:create", "vendor:select_offer",
            "product:view", "product:create", "product:adjust_stock"
        ],
        "staff": [
            {"username": "supply_mgr", "email": "supply@gacl.test", "first_name": "Priya", "last_name": "Akter", "designation": "Supply Chain Manager"},
            {"username": "procurement_officer", "email": "procurement@gacl.test", "first_name": "Arif", "last_name": "Hossain", "designation": "Procurement Officer"}
        ]
    }
]


class Command(BaseCommand):
    help = "Seed section permission groups and staff accounts assigned to section roles with granular sub-permissions."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seeding section permission groups, granular sub-permissions, and staff accounts..."))
        
        with transaction.atomic():
            emp_counter = 101
            total_staff_seeded = 0
            total_groups_seeded = 0

            for sec in SECTION_GROUPS:
                # 1. Ensure permissions exist
                group_perms = []
                for perm_name in sec["permissions"]:
                    p, _ = PermissonModel.objects.get_or_create(name=perm_name)
                    group_perms.append(p)

                # 2. Create Group and set permissions
                group, _ = GroupModel.objects.get_or_create(name=sec["group_name"])
                group.permission.set(group_perms)
                total_groups_seeded += 1

                # 3. Create Staff users and assign to group
                for sdata in sec["staff"]:
                    user, u_created = User.objects.get_or_create(
                        username=sdata["username"],
                        defaults={
                            "email": sdata["email"],
                            "first_name": sdata["first_name"],
                            "last_name": sdata["last_name"],
                            "is_staff": True,
                            "is_active": True,
                        }
                    )
                    if u_created or not user.check_password("staff1234"):
                        user.set_password("staff1234")
                        user.save()

                    # Assign user to group
                    assign, _ = AssignGroupPermission.objects.get_or_create(user=user)
                    assign.group.add(group)

                    # Staff Profile
                    StaffProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            "staff_ID": f"EMP{emp_counter:03d}",
                            "designation": sdata["designation"],
                            "phone": f"017{random.randint(10000000, 99999999)}",
                            "guest_allowed": True,
                        }
                    )
                    emp_counter += 1
                    total_staff_seeded += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {total_groups_seeded} section groups with granular action sub-permissions and {total_staff_seeded} departmental staff members!"
        ))
        self.stdout.write(self.style.SUCCESS("All staff user passwords set to: staff1234"))
