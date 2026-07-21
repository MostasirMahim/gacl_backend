import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.conf import settings
from account.models import GroupModel, AssignGroupPermission, PermissonModel


class Command(BaseCommand):
    help = "Bootstraps superuser account safely and attaches super_admin group."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting superadmin bootstrap...")
        
        # 1. Ensure authorization infrastructure is seeded
        super_admin_group = GroupModel.objects.filter(name="super_admin").first()
        if not super_admin_group or super_admin_group.permission.count() == 0:
            self.stdout.write("Authorization infrastructure missing or unseeded. Running 'bootstrap_auth'...")
            call_command("bootstrap_auth")
            super_admin_group = GroupModel.objects.filter(name="super_admin").first()

        # 2. Extract superadmin credentials from env / settings / fallbacks
        username = getattr(settings, "SUPER_ADMIN_USERNAME", os.getenv("SUPER_ADMIN_USERNAME", "admin"))
        email = getattr(settings, "SUPER_ADMIN_EMAIL", os.getenv("SUPER_ADMIN_EMAIL", "admin@gacl.test"))
        password = getattr(settings, "SUPER_ADMIN_PASSWORD", os.getenv("SUPER_ADMIN_PASSWORD", "admin1234"))

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            user.role = "SUPERADMIN"
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created successfully."))
        else:
            user.is_superuser = True
            user.is_staff = True
            user.email = email
            user.role = "SUPERADMIN"
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' updated successfully."))

        # 3. Assign super_admin group to user
        if super_admin_group:
            assign_group, _ = AssignGroupPermission.objects.get_or_create(user=user)
            if not assign_group.group.filter(id=super_admin_group.id).exists():
                assign_group.group.add(super_admin_group)
                assign_group.save()
            self.stdout.write(self.style.SUCCESS(f"Assigned 'super_admin' group to user '{username}'."))

        self.stdout.write(self.style.SUCCESS("Superadmin bootstrap completed successfully."))
