from rest_framework.permissions import BasePermission
from .models import AssignGroupPermission, GroupModel, PermissonModel
import pdb
from django.core.cache import cache


class HasCustomPermission(BasePermission):
    required_permission = None
    action_permissions = None  # e.g. {'GET': 'section:view', 'POST': 'section:create', 'PUT': 'section:edit', 'DELETE': 'section:delete'}

    def has_permission(self, request, view):
        if not request.user or request.user.is_anonymous:
            return False

        user = request.user
        if getattr(user, 'is_superuser', False):
            return True

        if self.required_permission is None and not getattr(self, 'action_permissions', None):
            return False

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

            cache.set(cache_key, list(user_permissions), timeout=60*5)
        else:
            user_permissions = set(user_permissions)

        # Check action sub-permission if configured for current HTTP method
        target_perm = None
        if hasattr(self, 'action_permissions') and isinstance(self.action_permissions, dict):
            target_perm = self.action_permissions.get(request.method)

        if target_perm:
            # Grant access if user has specific sub-permission OR master section permission
            return target_perm in user_permissions or self.required_permission in user_permissions

        return self.required_permission in user_permissions
