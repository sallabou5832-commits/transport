from rest_framework.permissions import SAFE_METHODS, BasePermission

from configuration.regles import roles_configurables_par
from core.models import Role

ROLES_JURIDIQUE_TECHNIQUE = {Role.RESPONSABLE_JURIDIQUE, Role.DIRECTEUR_TECHNIQUE}
ROLES_FINANCE = {Role.DIRECTEUR_FINANCIER, Role.PDG, Role.SECRETAIRE_GENERAL, Role.SUPERADMIN}


class IsDrh(BasePermission):
    """DRH uniquement, lecture comprise (données RH : pas de transparence par défaut)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.DRH)


class IsDrhOrOwnerReadOnly(BasePermission):
    """Le DRH a tous les droits sur les dossiers. Les autres les lisent seulement : chacun le sien, et chaque échelon ceux des postes
    placés sous son autorité (configuration hiérarchique, `configuration.regles`)."""

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
        return request.method in SAFE_METHODS and (obj.agent_id == user.id or obj.agent.role in roles_configurables_par(user.role))


class IsResponsableJuridiqueOuDirecteurTechnique(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_JURIDIQUE_TECHNIQUE)


class IsFinance(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_FINANCE)


class PeutVoirLaConformite(BasePermission):
    """Le tableau de conformité réglementaire : partagé entre le QHSE et le juridique, lu aussi par le technique (assurances et
    contrôles de ses véhicules), l'exploitation et la direction. Données d'une compagnie : pas de superadmin."""

    ROLES = {
        Role.QHSE, Role.RESPONSABLE_JURIDIQUE, Role.DIRECTEUR_TECHNIQUE, Role.DIRECTEUR_EXPLOITATION, Role.PDG, Role.SECRETAIRE_GENERAL,
    }

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.company_id is not None and user.role in self.ROLES)


class PeutGererLesModeles(BasePermission):
    """La bibliothèque de modèles juridiques : tout poste de la compagnie la consulte (filtrée par pôle), le responsable juridique la tient."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.company_id is not None):
            return False
        return request.method in SAFE_METHODS or user.role == Role.RESPONSABLE_JURIDIQUE


class PeutVoirLeReportingJuridique(BasePermission):
    """Le reporting remonté à la Direction Générale : le juridique qui l'établit, le PDG et son secrétaire général qui le lisent."""

    ROLES = {Role.RESPONSABLE_JURIDIQUE, Role.PDG, Role.SECRETAIRE_GENERAL}

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.company_id is not None and user.role in self.ROLES)
