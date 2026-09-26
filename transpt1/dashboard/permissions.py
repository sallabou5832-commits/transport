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


class PeutVoirLaCarte(BasePermission):
    """La carte du réseau (position des cars) : régulation, direction, QHSE, technique. Le superadmin n'a pas de compagnie."""

    def has_permission(self, request, view):
        from personnel_roulant.permissions import ROLES_SUIVI_TRAJETS

        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_SUIVI_TRAJETS and user.company_id is not None)


class PeutVoirLaSanteDeLaGare(BasePermission):
    """La santé d'une gare : son chef pour la sienne, et ceux qui pilotent l'exploitation pour la gare de leur choix."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.company_id is not None and user.role in ROLES_EXPLOITATION | {Role.CHEF_GARE}
        )
