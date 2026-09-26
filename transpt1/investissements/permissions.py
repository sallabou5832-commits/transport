from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

# Ceux qui déposent une demande : le technique (achat de cars), l'exploitation (ouverture de ligne), la finance.
ROLES_DEMANDEURS = {Role.DIRECTEUR_TECHNIQUE, Role.DIRECTEUR_EXPLOITATION, Role.DIRECTEUR_FINANCIER}
# Ceux qui voient toutes les demandes : celui qui décide, son secrétaire général, et la finance qui doit les budgéter.
ROLES_SUPERVISION = {Role.PDG, Role.SECRETAIRE_GENERAL, Role.DIRECTEUR_FINANCIER}


class PeutGererLesInvestissements(BasePermission):
    """Lire : les demandeurs (leurs demandes) et la supervision (toutes). Déposer : les demandeurs. Décider : voir `IsPdg`."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.company_id is not None):
            return False
        if request.method in SAFE_METHODS:
            return user.role in ROLES_DEMANDEURS | ROLES_SUPERVISION
        return user.role in ROLES_DEMANDEURS
