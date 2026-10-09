from rest_framework.permissions import BasePermission

from .models import Role


class IsAdminRole(BasePermission):
    message = "This action requires the ADMIN role."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.ADMIN)
