from rest_framework.permissions import BasePermission
from .models import AssignGroupPermission, GroupModel, PermissonModel
from django.core.cache import cache
from .protected_urls import get_required_permission_for_path


class HasCustomPermission(BasePermission):
    required_permission = None
    action_permissions = None

    def has_permission(self, request, view):
        if not request.user or request.user.is_anonymous:
            return False

        user = request.user
        if getattr(user, 'is_superuser', False):
            return True

        cache_key = f"user_permissions_{user.id}"
        user_permissions = cache.get(cache_key)
        if user_permissions is None:
            all_user_groups = AssignGroupPermission.objects.filter(
                user=user).prefetch_related("group__permission")
            user_permissions = set()

            for assign_group in all_user_groups:
                for group in assign_group.group.all():
                    for perm in group.permission.all():
                        user_permissions.add(perm.name)

            if not getattr(user, 'is_staff', False) and not getattr(user, 'is_superuser', False):
                member_group = GroupModel.objects.filter(name="club_member").prefetch_related("permission").first()
                if member_group:
                    for perm in member_group.permission.all():
                        user_permissions.add(perm.name)

            cache.set(cache_key, list(user_permissions), timeout=60*5)
        else:
            user_permissions = set(user_permissions)

        # 1. First check centralized URL path pattern registry
        path_permission = get_required_permission_for_path(request.path)
        if path_permission:
            return path_permission in user_permissions

        # 2. Second check action_permissions dictionary if present
        target_perm = None
        if hasattr(self, 'action_permissions') and isinstance(self.action_permissions, dict):
            target_perm = self.action_permissions.get(request.method)

        if target_perm:
            return target_perm in user_permissions

        # 3. Fallback to view's required_permission
        if self.required_permission:
            return self.required_permission in user_permissions

        return False
