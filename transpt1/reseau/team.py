"""Équipe locale d'une gare : qui la compose, et qui l'affecte.

Le chef de gare affecte guichetiers et bagagistes à SA gare ; le directeur des opérations, le secrétaire général et le
PDG peuvent affecter n'importe quel agent de l'équipe locale à n'importe quelle gare de la compagnie.
"""

from core.models import Role

# Les postes d'une équipe locale (cahier des charges : « affectation des équipes locales (guichetiers, bagagistes) »).
ROLES_EQUIPE_LOCALE = {Role.GUICHETIER, Role.BAGAGISTE}
# Ceux qui composent les équipes, et ceux qui peuvent le faire pour toute gare.
ROLES_AFFECTATION = {Role.CHEF_GARE, Role.DIRECTEUR_EXPLOITATION, Role.SECRETAIRE_GENERAL, Role.PDG, Role.SUPERADMIN}
ROLES_AFFECTATION_TOUTES_GARES = ROLES_AFFECTATION - {Role.CHEF_GARE}
