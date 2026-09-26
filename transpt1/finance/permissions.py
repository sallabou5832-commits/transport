from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

# La finance tient la comptabilité ; le PDG et son secrétaire général la lisent (trésorerie « visible du PDG »).
ROLES_ECRITURE = {Role.DIRECTEUR_FINANCIER}
ROLES_LECTURE = ROLES_ECRITURE | {Role.PDG, Role.SECRETAIRE_GENERAL}


class PeutGererLaFinance(BasePermission):
    """Lire : finance, PDG, secrétaire général. Écrire (dépenses, budgets, fournisseurs, factures, réglages) : la finance."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.company_id is not None):
            return False
        return user.role in (ROLES_LECTURE if request.method in SAFE_METHODS else ROLES_ECRITURE)
