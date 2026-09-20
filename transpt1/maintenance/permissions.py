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


class CanManagePiece(BasePermission):
    """Reads (catalogue lookup, low-stock alert) are open to everyone.

    Only magasinier, chef_atelier and directeur_technique may create, update
    or delete a Piece — the same people who record stock movements against it.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_SORTIE_PIECE)


ROLES_CREATION_ORDRE_REPARATION = {
    Role.CHEF_ATELIER,
    Role.DIRECTEUR_TECHNIQUE,
    Role.DIRECTEUR_EXPLOITATION,
    Role.SECRETAIRE_GENERAL,
    Role.PDG,
    Role.SUPERADMIN,
}


class CanCreateOrdreReparation(BasePermission):
    """Only workshop/operations management may open a new repair order.

    Leaves every other method (read, update, delete) untouched — those are
    governed by CanManageOrdreReparation below.
    """

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_CREATION_ORDRE_REPARATION)


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
