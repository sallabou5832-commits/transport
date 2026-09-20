from rest_framework.permissions import BasePermission

from core.models import Role

ROLES_DIRECTION = {Role.PDG, Role.SECRETAIRE_GENERAL, Role.QHSE}
ROLES_EXPLOITATION = {Role.DIRECTEUR_EXPLOITATION, Role.PDG, Role.SECRETAIRE_GENERAL}


class IsDirection(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_DIRECTION)


class IsQhse(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.QHSE)


class IsExploitation(BasePermission):
    """Vue d'ensemble de l'exploitation : les rôles qui pilotent gares, lignes et départs."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_EXPLOITATION)


class IsSuperadmin(BasePermission):
    """Vue de la plateforme (toutes les compagnies) : l'opérateur de la plateforme seulement."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.SUPERADMIN)
