from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

# `Role` is declared (in core/models.py) from the highest position in the company's
# org chart down to the most specialized/support roles. We reuse that declaration
# order as an implicit hierarchy instead of hard-coding a second, parallel list that
# would inevitably drift out of sync with it.
_ROLE_ORDER = list(Role)
_GUICHETIER_RANK = _ROLE_ORDER.index(Role.GUICHETIER)


def is_guichetier_or_above(role):
    """True if `role` is guichetier or ranks above it in the company hierarchy."""
    try:
        return _ROLE_ORDER.index(Role(role)) <= _GUICHETIER_RANK
    except ValueError:
        return False


class IsGuichetierOrAboveAlways(BasePermission):
    """Every method (reads included) requires guichetier-or-above.

    Used for the cash-closing report, which exposes a guichetier's sales figures
    and should not be readable by roles outside the sales hierarchy.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_guichetier_or_above(user.role))


class IsGuichetierOrAboveWrite(BasePermission):
    """Reads are open to any authenticated same-company user; only creating,
    updating or deleting a ticket requires guichetier-or-above.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsGuichetierOrAboveAlways().has_permission(request, view)


DISPATCH_ROLES = {
    Role.CHEF_LIGNE,
    Role.CHEF_GARE,
    Role.DIRECTEUR_EXPLOITATION,
    Role.SECRETAIRE_GENERAL,
    Role.PDG,
    Role.SUPERADMIN,
}


class IsDispatchManagerAlways(BasePermission):
    """Rôles de planification, lecture comprise : réservé à ce qui n'est pas de la transparence
    par défaut (ici, l'annuaire des chauffeurs libres proposés pour un remplacement).
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in DISPATCH_ROLES)


class IsDispatchManagerOrReadOnly(BasePermission):
    """Reads are open to any authenticated same-company user; scheduling a
    depart (create/update/delete) is reserved to dispatch/management roles.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in DISPATCH_ROLES)
