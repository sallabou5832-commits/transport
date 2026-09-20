from rest_framework.permissions import BasePermission

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


class IsGuichetierOrAbove(BasePermission):
    """Restricts access to guichetiers and roles above them in the hierarchy.

    Combine with IsSameCompany for object-level company scoping.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_guichetier_or_above(user.role))
