from rest_framework.permissions import BasePermission

from core.models import Role
from tutelle.models import CompteTutelle

# Les flux échangés avec la tutelle : suivis par le QHSE (sécurité, trafic) et le responsable juridique (conformité)
# de la compagnie — les deux voient tous les flux, quel qu'en soit le type : chacun sait ce que l'autre a reçu.
ROLES_SUIVI_TUTELLE = {Role.QHSE, Role.RESPONSABLE_JURIDIQUE}


class EstCompteTutelle(BasePermission):
    """Réservé à un compte tutelle authentifié par clé d'API (voir `tutelle.authentication`) — jamais à un compte
    interne d'une compagnie, même le PDG par son propre jeton JWT."""

    def has_permission(self, request, view):
        return isinstance(request.user, CompteTutelle)


class PeutSuivreLesFluxTutelle(BasePermission):
    """Consulter et traiter les flux de sa compagnie : le QHSE et le responsable juridique — jamais un compte
    tutelle (`request.user` y est un `CompteTutelle`, pas un `core.User` : pas de `role`, pas de `company_id`)."""

    def has_permission(self, request, view):
        user = request.user
        if isinstance(user, CompteTutelle):
            return False
        return bool(user and user.is_authenticated and user.role in ROLES_SUIVI_TUTELLE and user.company_id is not None)
