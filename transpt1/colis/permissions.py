from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role

# Enregistrer, charger et remettre un colis : le bagagiste, et la supervision qui peut agir à sa place.
ROLES_ECRITURE_COLIS = {
    Role.BAGAGISTE, Role.CHEF_GARE, Role.CHEF_LIGNE, Role.DIRECTEUR_EXPLOITATION, Role.SECRETAIRE_GENERAL, Role.PDG,
    Role.SUPERADMIN,
}
# Annuler un enregistrement (l'argent est à rendre) et renvoyer un code de retrait : la supervision, pas le bagagiste.
ROLES_SUPERVISION_COLIS = ROLES_ECRITURE_COLIS - {Role.BAGAGISTE}
# Voir les colis (noms et téléphones des clients : pas de transparence par défaut). Le guichetier renseigne le voyageur,
# le contrôleur compare la charge à ce qui a été enregistré, le chauffeur sait ce qu'il transporte, le QHSE contrôle.
ROLES_LECTURE_COLIS = ROLES_ECRITURE_COLIS | {
    Role.GUICHETIER, Role.CONTROLEUR_LIGNE, Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS, Role.QHSE,
}


class CanUseColis(BasePermission):
    """Lecture réservée à ROLES_LECTURE_COLIS ; écriture à ROLES_ECRITURE_COLIS (les actions de supervision ajoutent
    leur propre contrôle)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return user.role in ROLES_LECTURE_COLIS
        return user.role in ROLES_ECRITURE_COLIS
