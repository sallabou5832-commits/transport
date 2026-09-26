from rest_framework.permissions import BasePermission

from core.models import Company, Role


class IsSameCompany(BasePermission):
    """Object-level permission restricting access to the requesting user's own company.

    A superadmin (no company, operates the platform) is exempt and can access any
    company's data.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role == Role.SUPERADMIN:
            return True
        if user.company_id is None:
            return False

        obj_company_id = obj.id if isinstance(obj, Company) else getattr(obj, "company_id", None)
        return obj_company_id is not None and obj_company_id == user.company_id


class IsPdg(BasePermission):
    """Les pouvoirs d'intervention directe (suspendre un compte, valider un investissement) sont ceux du PDG."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.PDG and user.company_id is not None)
