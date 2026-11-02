from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role
from lien_billetterie.models import CleLienBilletterie

# Le mode de billetterie et les clés du lien : le directeur des opérations, qui pilote la billetterie, et le PDG.
ROLES_GESTION_LIEN = {Role.PDG, Role.DIRECTEUR_EXPLOITATION}
# Déposer un fichier de ventes : eux, et le chef de gare pour les départs de sa gare.
ROLES_IMPORT = ROLES_GESTION_LIEN | {Role.CHEF_GARE}


def _agent_de_compagnie(user):
    return bool(
        user and not isinstance(user, CleLienBilletterie) and user.is_authenticated and user.company_id is not None
    )


class EstLeLogicielDeLaCompagnie(BasePermission):
    """Réservé au logiciel de billetterie d'une compagnie, authentifié par sa clé (voir `lien_billetterie.authentication`)."""

    def has_permission(self, request, view):
        return isinstance(request.user, CleLienBilletterie)


class PeutVoirOuReglerLeModeDeBilletterie(BasePermission):
    """Tout agent de la compagnie lit son mode de billetterie (les écrans de vente s'y adaptent) ; le PDG et le directeur
    des opérations le règlent."""

    def has_permission(self, request, view):
        user = request.user
        if not _agent_de_compagnie(user):
            return False
        return request.method in SAFE_METHODS or user.role in ROLES_GESTION_LIEN


class PeutGererLesCles(BasePermission):
    def has_permission(self, request, view):
        return _agent_de_compagnie(request.user) and request.user.role in ROLES_GESTION_LIEN


class PeutImporterDesVentes(BasePermission):
    def has_permission(self, request, view):
        return _agent_de_compagnie(request.user) and request.user.role in ROLES_IMPORT
