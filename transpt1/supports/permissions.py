from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

ROLES_JURIDIQUE_TECHNIQUE = {Role.RESPONSABLE_JURIDIQUE, Role.DIRECTEUR_TECHNIQUE}
ROLES_FINANCE = {Role.DIRECTEUR_FINANCIER, Role.PDG, Role.SECRETAIRE_GENERAL, Role.SUPERADMIN}


class IsDrhOrOwnerReadOnly(BasePermission):
    """DRH has full access. Any other user may only read their own dossier."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role == Role.DRH

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == Role.DRH:
            return True
        return request.method in SAFE_METHODS and obj.agent_id == user.id


class IsResponsableJuridiqueOuDirecteurTechnique(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_JURIDIQUE_TECHNIQUE)


class IsFinance(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_FINANCE)
