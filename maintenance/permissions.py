from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

ROLES_SORTIE_PIECE = {Role.MAGASINIER, Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE}


class CanManageStockMovement(BasePermission):
    """Only magasinier, chef_atelier and directeur_technique may touch stock movements."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_SORTIE_PIECE)


class CanManageOrdreReparation(BasePermission):
    """Read access is unrestricted (subject to company scoping elsewhere).

    Only chef_atelier, or the mecanicien assigned to that specific ordre, may
    modify or delete it.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.role == Role.CHEF_ATELIER:
            return True
        return obj.mecanicien_id == user.id
