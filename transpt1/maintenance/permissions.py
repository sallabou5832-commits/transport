from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

ROLES_SORTIE_PIECE = {Role.MAGASINIER, Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE}


class CanManageStockMovement(BasePermission):
    """Magasinier, chef d'atelier and directeur technique may record any stock movement ; the mécanicien
    may record one too (the stock is updated at every outgoing part he registers), but only against an
    order assigned to him — that last rule is checked by the serializer, which knows the order."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method == "POST" and user.role == Role.MECANICIEN:
            return True
        return user.role in ROLES_SORTIE_PIECE


class CanManagePiece(BasePermission):
    """Reads (catalogue lookup, low-stock alert) are open to everyone.

    Only magasinier, chef_atelier and directeur_technique may create, update
    or delete a Piece — the same people who record stock movements against it.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_SORTIE_PIECE)


class PeutRecevoirEtInventorier(BasePermission):
    """Réceptions et inventaires des pièces : tous les lisent ; le magasinier, le chef d'atelier et le directeur technique les
    enregistrent (les mêmes que pour les sorties ; le mécanicien, lui, ne fait que sortir les pièces de ses ordres)."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_SORTIE_PIECE)


ROLES_CREATION_ORDRE_REPARATION = {
    Role.CHEF_ATELIER,
    Role.DIRECTEUR_TECHNIQUE,
    Role.DIRECTEUR_EXPLOITATION,
    Role.SECRETAIRE_GENERAL,
    Role.PDG,
    Role.SUPERADMIN,
}


class CanCreateOrdreReparation(BasePermission):
    """Only workshop/operations management may open a new repair order.

    Leaves every other method (read, update, delete) untouched — those are
    governed by CanManageOrdreReparation below.
    """

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role in ROLES_CREATION_ORDRE_REPARATION)


class CanManageOrdreReparation(BasePermission):
    """Read access is unrestricted (subject to company scoping elsewhere).

    Only chef_atelier, or the mecanicien assigned to that specific ordre, may
    modify or delete it.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.role == Role.CHEF_ATELIER:
            return True
        return obj.mecanicien_id == user.id


class _RolesDeLaCompagnie(BasePermission):
    """Réservé à `ROLES`, pour une compagnie (le superadmin, sans compagnie, n'y a pas accès : ce sont des données d'atelier)."""

    ROLES = set()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.company_id is not None and user.role in self.ROLES)


class PeutPiloterLAtelier(_RolesDeLaCompagnie):
    """Ordonner la file des réparations, fixer une urgence ou un délai, répartir les interventions : le directeur technique et
    le chef d'atelier."""

    ROLES = {Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER}


class PeutVoirLesIntervenants(_RolesDeLaCompagnie):
    """La liste des intervenants de l'atelier, pour confier un ordre à un collègue : l'atelier et le directeur technique."""

    ROLES = {Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER, Role.MECANICIEN}


class PeutGererLesPlans(BasePermission):
    """Les plans d'entretien se lisent comme tout le reste ; les déclarer et les modifier revient au technique."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or (
            user.company_id is not None and user.role in {Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER}
        )


class PeutUtiliserLesDemandesDePieces(BasePermission):
    """Demander une pièce : l'atelier (mécanicien, chef d'atelier). La voir : l'atelier, le magasinier qui la sert, le directeur
    technique. Servir ou refuser : le magasinier (action dédiée)."""

    LECTURE = {Role.MAGASINIER, Role.MECANICIEN, Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE}
    ECRITURE = {Role.MECANICIEN, Role.CHEF_ATELIER}

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.company_id is not None):
            return False
        return user.role in (self.LECTURE if request.method in SAFE_METHODS else self.ECRITURE)


class PeutServirLesDemandes(_RolesDeLaCompagnie):
    ROLES = {Role.MAGASINIER}


class PeutVoirLesSuggestionsDeCommande(_RolesDeLaCompagnie):
    ROLES = {Role.MAGASINIER, Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER}


class PeutVoirLaFicheVehicule(_RolesDeLaCompagnie):
    """L'historique technique d'un véhicule : l'atelier, le magasin, l'exploitation, la direction, le QHSE."""

    ROLES = {
        Role.DIRECTEUR_TECHNIQUE, Role.CHEF_ATELIER, Role.MECANICIEN, Role.MAGASINIER, Role.DIRECTEUR_EXPLOITATION,
        Role.PDG, Role.SECRETAIRE_GENERAL, Role.QHSE,
    }


class PeutVoirLeBesoinDeRenouvellement(_RolesDeLaCompagnie):
    """Le rapport pour la Direction Générale : le PDG et son secrétaire général, le technique qui le nourrit, l'exploitation et
    la finance qui en tirent des décisions."""

    ROLES = {
        Role.DIRECTEUR_TECHNIQUE, Role.PDG, Role.SECRETAIRE_GENERAL, Role.DIRECTEUR_EXPLOITATION, Role.DIRECTEUR_FINANCIER,
    }
