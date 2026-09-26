from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role
from reseau.lignes import DECIDEURS, DEMANDEURS
from reseau.team import ROLES_AFFECTATION, ROLES_AFFECTATION_TOUTES_GARES


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


class CanManageAffectation(BasePermission):
    """Composer les équipes locales : le chef de gare pour SA gare, la direction des opérations pour toutes.

    La lecture est filtrée par le ViewSet (chacun voit son affectation, les rôles de pilotage voient toutes)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or user.role in ROLES_AFFECTATION

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return user.role in ROLES_AFFECTATION_TOUTES_GARES or obj.gare.chef_id == user.id


class _RolesDeLaCompagnie(BasePermission):
    ROLES = set()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.company_id is not None and user.role in self.ROLES)


class PeutChangerLigne(_RolesDeLaCompagnie):
    """Fermer ou rouvrir une ligne : la demander (chef de ligne, chef de gare) ou l'appliquer (direction des opérations, PDG)."""

    ROLES = DECIDEURS | DEMANDEURS


class PeutVoirLesChangements(_RolesDeLaCompagnie):
    """Voir les demandes de fermeture : ceux qui les font (les leurs) et ceux qui les décident (toutes)."""

    ROLES = DECIDEURS | DEMANDEURS


class PeutArbitrer(_RolesDeLaCompagnie):
    """Décider : valider une fermeture de ligne, réaffecter un véhicule d'une gare à l'autre."""

    ROLES = DECIDEURS
