from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

CHAUFFEUR_ROLES = {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS}


class IsOwnerChauffeurOrAbove(BasePermission):
    """Read access is unrestricted (subject to company scoping elsewhere).

    For write operations: a chauffeur_principal/chauffeur_relais may only act on
    records where they are the chauffeur. Every other role is unrestricted here.
    """

    def get_chauffeur_id(self, obj):
        raise NotImplementedError

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.role not in CHAUFFEUR_ROLES:
            return True
        return self.get_chauffeur_id(obj) == user.id


class IsOwnFeuilleDeRoute(IsOwnerChauffeurOrAbove):
    def get_chauffeur_id(self, obj):
        return obj.chauffeur_id


class IsOwnChecklist(IsOwnerChauffeurOrAbove):
    def get_chauffeur_id(self, obj):
        return obj.feuille_de_route.chauffeur_id


class IsOwnIncident(IsOwnerChauffeurOrAbove):
    def get_chauffeur_id(self, obj):
        return obj.chauffeur_id


ROLES_GESTION_ROULANT = CHAUFFEUR_ROLES | {
    Role.CHEF_LIGNE,
    Role.CHEF_GARE,
    Role.DIRECTEUR_EXPLOITATION,
    Role.CONTROLEUR_LIGNE,
    Role.QHSE,
    Role.SECRETAIRE_GENERAL,
    Role.PDG,
    Role.SUPERADMIN,
}


class IsRoulantManagerOrReadOnly(BasePermission):
    """Reads are open to any authenticated same-company user.

    Writes are reserved to operational/safety roles (chauffeurs included —
    their access is then narrowed to their own records by the Is Own*
    permission classes above).
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_GESTION_ROULANT)


class IsQhseOuDirecteurExploitation(BasePermission):
    """Restricts access to QHSE, directeur exploitation, and superadmin."""

    ALLOWED_ROLES = {Role.QHSE, Role.DIRECTEUR_EXPLOITATION, Role.SUPERADMIN}

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.ALLOWED_ROLES)
