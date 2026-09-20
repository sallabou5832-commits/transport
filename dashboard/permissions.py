from rest_framework.permissions import BasePermission

from core.models import Role

ROLES_DIRECTION = {Role.PDG, Role.SECRETAIRE_GENERAL, Role.QHSE}


class IsDirection(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_DIRECTION)


class IsQhse(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.QHSE)
