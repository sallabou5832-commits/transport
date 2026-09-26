from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

# Le secrétariat de la direction : rédiger les notes de service, tenir l'agenda, classer les archives.
ROLES_SECRETARIAT = {Role.SECRETAIRE_GENERAL, Role.PDG}
# L'agenda de la direction se partage entre la direction générale et les directeurs de pôle.
ROLES_AGENDA = ROLES_SECRETARIAT | {
    Role.QHSE, Role.DIRECTEUR_EXPLOITATION, Role.DIRECTEUR_TECHNIQUE, Role.DIRECTEUR_FINANCIER, Role.DRH, Role.RESPONSABLE_JURIDIQUE,
}
# Voir les messages directs d'une gare : son chef pour les siens, et l'exploitation pour toutes les gares.
ROLES_SUPERVISION_MESSAGES = {Role.DIRECTEUR_EXPLOITATION, Role.PDG, Role.SECRETAIRE_GENERAL}


class _AvecCompagnie(BasePermission):
    def _connecte(self, request):
        user = request.user
        return bool(user and user.is_authenticated and user.company_id is not None)


class PeutLireLesNotes(_AvecCompagnie):
    """Tout poste de la compagnie lit les notes qui le visent ; seul le secrétariat en rédige."""

    def has_permission(self, request, view):
        if not self._connecte(request):
            return False
        return request.method in SAFE_METHODS or request.user.role in ROLES_SECRETARIAT


class PeutTenirLAgenda(_AvecCompagnie):
    def has_permission(self, request, view):
        if not self._connecte(request):
            return False
        if request.method in SAFE_METHODS:
            return request.user.role in ROLES_AGENDA
        return request.user.role in ROLES_SECRETARIAT


class PeutClasserLesArchives(_AvecCompagnie):
    """Les dossiers administratifs : le secrétariat de la direction, en lecture comme en écriture."""

    def has_permission(self, request, view):
        return self._connecte(request) and request.user.role in ROLES_SECRETARIAT


class PeutEcrireAuxEquipes(_AvecCompagnie):
    """Envoyer un message direct : le chef de gare. Le lire : lui (les siens) et l'exploitation."""

    def has_permission(self, request, view):
        if not self._connecte(request):
            return False
        if request.method in SAFE_METHODS:
            return request.user.role == Role.CHEF_GARE or request.user.role in ROLES_SUPERVISION_MESSAGES
        return request.user.role == Role.CHEF_GARE
