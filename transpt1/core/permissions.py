from rest_framework.permissions import SAFE_METHODS, BasePermission

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


class PeutGererLesComptes(BasePermission):
    """Créer les comptes du personnel, les modifier, réinitialiser un mot de passe : le PDG, et le DRH si le règlement
    intérieur de la compagnie le lui permet (règle `drh_gere_les_comptes`, non permise par défaut, comme avant)."""

    message = "La gestion des comptes est réservée au PDG et au DRH."

    def has_permission(self, request, view):
        from configuration.regles import REGLEMENT
        from configuration.services import reglement_de

        user = request.user
        if not (user and user.is_authenticated and user.company_id is not None):
            return False
        if user.role == Role.PDG:
            return True
        if user.role != Role.DRH:
            return False
        if not reglement_de(user.company_id)["drh_gere_les_comptes"]:
            self.message = REGLEMENT["drh_gere_les_comptes"].refus
            return False
        return True


class PeutTenirLaFicheCompagnie(BasePermission):
    """La fiche de la compagnie (« Ma compagnie ») : chacun lit celle de sa compagnie, seul le PDG la modifie."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.company_id is not None):
            return False
        return request.method in SAFE_METHODS or user.role == Role.PDG
