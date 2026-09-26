"""Qui voit et qui écrit quoi en RH. Le principe du cahier des charges est la configuration hiérarchique : chaque échelon voit les
dossiers des postes placés directement sous son autorité (`configuration.regles`), le DRH et le PDG voient tout, chacun voit le sien.
Les données sont celles d'une compagnie : pas d'accès sans compagnie (donc pas pour le superadmin)."""

from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from configuration.regles import roles_configurables_par
from core.models import Role

# Contrat, évaluations, discipline : le DRH et le PDG les lisent tous.
DOSSIERS_LARGE = {Role.DRH, Role.PDG}
# Formations obligatoires : aussi le QHSE (sécurité routière) et le secrétaire général.
FORMATIONS_LARGE = {Role.DRH, Role.QHSE, Role.PDG, Role.SECRETAIRE_GENERAL}
# Recrutement : vu de la direction, tenu par le DRH.
RECRUTEMENT_LECTURE = {Role.DRH, Role.PDG, Role.SECRETAIRE_GENERAL}


def dans_une_compagnie(user):
    return bool(user and user.is_authenticated and user.company_id is not None)


def visibles(queryset, user, larges, champ="agent"):
    """Les lignes d'un modèle rattaché à un agent que `user` a le droit de lire : tout pour les rôles `larges`, sinon les siennes et celles
    des postes sous son autorité."""
    queryset = queryset.filter(company_id=user.company_id)
    if user.role in larges:
        return queryset
    return queryset.filter(Q(**{champ: user}) | Q(**{f"{champ}__role__in": roles_configurables_par(user.role)}))


def agents_visibles(user, larges):
    """Les agents actifs dont `user` peut lire les informations RH (voir `visibles`)."""
    from django.contrib.auth import get_user_model

    agents = get_user_model().objects.filter(company_id=user.company_id, is_active=True)
    if user.role in larges:
        return agents
    return agents.filter(Q(pk=user.pk) | Q(role__in=roles_configurables_par(user.role)))


def peut_evaluer(user, agent):
    """Le DRH évalue tout le monde ; un échelon évalue les postes directement sous son autorité."""
    return user.role == Role.DRH or agent.role in roles_configurables_par(user.role)


def permission(*, ecriture, lecture=None):
    """Lecture : `lecture` (ou tout agent de la compagnie si None, les données étant alors filtrées par la vue) ; écriture : `ecriture`."""

    class _Permission(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            if not dans_une_compagnie(user):
                return False
            if request.method in SAFE_METHODS:
                return lecture is None or user.role in lecture
            return user.role in ecriture

    return _Permission


class EstUnAgentDeCompagnie(BasePermission):
    """Tout poste d'une compagnie (accès en libre-service : ses congés, ses doléances, ses formations)."""

    def has_permission(self, request, view):
        return dans_une_compagnie(request.user)


class EstDrh(BasePermission):
    def has_permission(self, request, view):
        return dans_une_compagnie(request.user) and request.user.role == Role.DRH


class PeutVoirLaSyntheseRh(BasePermission):
    """Les chiffres de l'effectif et de la gestion RH : le DRH, la direction."""

    def has_permission(self, request, view):
        return dans_une_compagnie(request.user) and request.user.role in DOSSIERS_LARGE | {Role.SECRETAIRE_GENERAL}


class PeutVoirLesLitiges(BasePermission):
    """Les doléances qui ont atteint le seuil de litige social : le responsable juridique, le DRH qui les instruit, le PDG."""

    def has_permission(self, request, view):
        return dans_une_compagnie(request.user) and request.user.role in {Role.RESPONSABLE_JURIDIQUE, Role.DRH, Role.PDG}


PermissionObligations = permission(lecture=FORMATIONS_LARGE, ecriture={Role.DRH, Role.QHSE})
PermissionFormations = permission(ecriture={Role.DRH, Role.QHSE})
PermissionContrats = permission(ecriture={Role.DRH})
PermissionMesures = permission(ecriture={Role.DRH})
PermissionRecrutement = permission(lecture=RECRUTEMENT_LECTURE, ecriture={Role.DRH})
