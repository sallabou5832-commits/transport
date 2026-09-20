from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role


class CanManageOwnGare(BasePermission):
    """A chef_gare may only modify (or delete) the Gare they lead.

    Read access and every other role are unaffected — this only tightens
    write access for the chef_gare role specifically.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.role != Role.CHEF_GARE:
            return True
        return obj.chef_id == user.id


class _IsNetworkManagerOrReadOnly(BasePermission):
    """Reads are open to any authenticated same-company user; only the
    roles listed in `ROLES` may create, update or delete.
    """

    ROLES = set()

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.ROLES)


class IsGareManagerOrReadOnly(_IsNetworkManagerOrReadOnly):
    ROLES = {Role.CHEF_GARE, Role.DIRECTEUR_EXPLOITATION, Role.SECRETAIRE_GENERAL, Role.PDG, Role.SUPERADMIN}


class IsLigneManagerOrReadOnly(_IsNetworkManagerOrReadOnly):
    ROLES = {Role.CHEF_LIGNE, Role.DIRECTEUR_EXPLOITATION, Role.SECRETAIRE_GENERAL, Role.PDG, Role.SUPERADMIN}


class IsVehiculeManagerOrReadOnly(_IsNetworkManagerOrReadOnly):
    ROLES = {
        Role.DIRECTEUR_TECHNIQUE,
        Role.CHEF_ATELIER,
        Role.DIRECTEUR_EXPLOITATION,
        Role.SECRETAIRE_GENERAL,
        Role.PDG,
        Role.SUPERADMIN,
    }
