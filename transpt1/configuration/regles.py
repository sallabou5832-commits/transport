"""Règles de la configuration hiérarchique : qui configure qui, ce qui est configurable, valeurs par défaut.

Cahier des charges : « chaque échelon supérieur peut configurer le rôle et les paramètres de l'échelon directement
subordonné [...] dans le cadre fixé par la compagnie ». Le socle est livré calibré ; rien n'est à configurer pour
démarrer.
"""

from core.models import Role


class NiveauAutomatisation:
    """Fonctions automatisées proposées par défaut (encaissement unifié, clôture de caisse automatique, planning
    assisté...) : chaque compagnie active le niveau adapté à ses moyens et à l'aisance de chaque agent."""

    MANUEL = "manuel"  # l'agent fait tout lui-même : aucune aide, aucune action automatique
    ASSISTE = "assiste"  # le système propose (remplaçant, clôture prête...), l'agent valide
    AUTOMATIQUE = "automatique"  # le système le fait (clôture de caisse en fin de journée...) et l'agent contrôle
    ORDRE = (MANUEL, ASSISTE, AUTOMATIQUE)
    CHOIX = [(MANUEL, "Manuel"), (ASSISTE, "Assisté"), (AUTOMATIQUE, "Automatique")]


class NiveauGamification:
    """Ce que le poste voit du jeu : rien, un tableau sobre (points, missions), ou tout (classements, badges)."""

    AUCUN = "aucun"
    SOBRE = "sobre"  # points, missions et niveau ; ni classement, ni badges
    COMPLET = "complet"
    ORDRE = (AUCUN, SOBRE, COMPLET)
    CHOIX = [(AUCUN, "Aucune"), (SOBRE, "Sobre (sans classement)"), (COMPLET, "Complète")]


class AisanceNumerique:
    FAIBLE = "faible"
    MOYENNE = "moyenne"
    ELEVEE = "elevee"
    CHOIX = [(FAIBLE, "Peu à l'aise"), (MOYENNE, "À l'aise"), (ELEVEE, "Très à l'aise")]


# Qui configure qui : les rôles directement subordonnés à chaque échelon. Le PDG, qui fixe le cadre de la compagnie,
# peut en plus configurer n'importe quel poste (voir `peut_configurer`).
SUBORDONNES = {
    Role.PDG: {
        Role.SECRETAIRE_GENERAL, Role.QHSE, Role.DIRECTEUR_EXPLOITATION, Role.DIRECTEUR_TECHNIQUE, Role.DRH,
        Role.DIRECTEUR_FINANCIER, Role.RESPONSABLE_JURIDIQUE,
    },
    Role.DIRECTEUR_EXPLOITATION: {Role.CHEF_GARE, Role.CHEF_LIGNE, Role.CONTROLEUR_LIGNE},
    Role.CHEF_GARE: {Role.GUICHETIER, Role.BAGAGISTE},
    Role.CHEF_LIGNE: {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS},
    Role.DIRECTEUR_TECHNIQUE: {Role.MAGASINIER, Role.CHEF_ATELIER},
    Role.CHEF_ATELIER: {Role.MECANICIEN},
}
# Les postes du socle : tous les rôles métier (le superadmin n'est pas un poste de compagnie).
POSTES = [role for role in Role if role != Role.SUPERADMIN]


def subordonnes_directs(role):
    return set(SUBORDONNES.get(role, set()))


def roles_configurables_par(role):
    """Les postes qu'un rôle peut configurer : ses subordonnés directs ; pour le PDG, tous les postes de la compagnie
    (hors le sien : on ne se règle pas soi-même, le cadre de la compagnie s'en charge)."""
    if role == Role.PDG:
        return set(POSTES) - {Role.PDG}
    return subordonnes_directs(role)


def peut_configurer(role_demandeur, role_cible):
    return role_cible in roles_configurables_par(role_demandeur)


# Fonctions qu'un échelon peut retirer à un poste (« ce qu'un guichetier ou un bagagiste peut faire »). Chacune est
# vérifiée par le serveur au point indiqué : désactiver une fonction ne se contente pas de cacher un bouton.
FONCTIONS = {
    "vente_ticket": "Vendre des tickets",
    "enregistrement_colis": "Enregistrer des bagages et des colis",
    "planification_departs": "Planifier des départs",
    "cloture_caisse": "Clôturer sa caisse",
}

# Niveaux par défaut d'un poste (le socle « prêt à l'emploi »). Direction, secrétariat, RH, finance et juridique
# démarrent sur un tableau sobre, sans classement : usage professionnel avant tout.
AUTOMATISATION_PAR_DEFAUT = NiveauAutomatisation.ASSISTE
POSTES_SOBRES = {
    Role.SECRETAIRE_GENERAL, Role.DRH, Role.DIRECTEUR_FINANCIER, Role.RESPONSABLE_JURIDIQUE,
}


def gamification_par_defaut(role):
    return NiveauGamification.SOBRE if role in POSTES_SOBRES else NiveauGamification.COMPLET


def rang(niveau, ordre):
    return ordre.index(niveau)


def plafonner(niveau, plafond, ordre):
    """Le plus bas des deux : un poste ne dépasse jamais le cadre fixé par la compagnie."""
    return niveau if rang(niveau, ordre) <= rang(plafond, ordre) else plafond
