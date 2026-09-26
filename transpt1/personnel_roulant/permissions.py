from rest_framework.permissions import SAFE_METHODS, BasePermission

from billetterie.permissions import DISPATCH_ROLES
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


class IsQhseOrReadOnly(BasePermission):
    """Poser ou lever un blocage de sécurité est le pouvoir du QHSE ; tous les rôles de la compagnie le voient."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in {Role.QHSE, Role.SUPERADMIN})


class IsQhseOuDirecteurExploitation(BasePermission):
    """Restricts access to QHSE, directeur exploitation, and superadmin."""

    ALLOWED_ROLES = {Role.QHSE, Role.DIRECTEUR_EXPLOITATION, Role.SUPERADMIN}

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.ALLOWED_ROLES)


# Qui voit où sont les cars et la fatigue des conducteurs : la régulation, la direction, le QHSE et le technique.
ROLES_SUIVI_TRAJETS = set(DISPATCH_ROLES) | {Role.QHSE, Role.DIRECTEUR_TECHNIQUE}


# Voir les contrôles (billets, fraudes, infractions) : le contrôleur pour les siens, et ceux qui les exploitent.
ROLES_LECTURE_CONTROLES = {
    Role.CONTROLEUR_LIGNE, Role.QHSE, Role.DIRECTEUR_EXPLOITATION, Role.PDG, Role.SECRETAIRE_GENERAL, Role.CHEF_LIGNE,
    Role.CHEF_GARE, Role.SUPERADMIN,
}


class CanControler(BasePermission):
    """Contrôler à bord est le métier du contrôleur de ligne ; la lecture des contrôles est ouverte à ROLES_LECTURE_CONTROLES."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return user.role in ROLES_LECTURE_CONTROLES
        return user.role == Role.CONTROLEUR_LIGNE
