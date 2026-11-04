"""Règles de la configuration hiérarchique : qui configure qui, ce qui est configurable, valeurs par défaut.

Cahier des charges : « chaque échelon supérieur peut configurer le rôle et les paramètres de l'échelon directement
subordonné [...] dans le cadre fixé par la compagnie ». Le socle est livré calibré ; rien n'est à configurer pour
démarrer.
"""

from datetime import timedelta
from typing import NamedTuple

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


class DureeSession:
    """Combien de temps une session reste ouverte sans redemander le mot de passe (« rester connecté »). Chacun choisit à la
    connexion, sans dépasser le plafond de la compagnie, que le PDG peut abaisser et qu'un supérieur peut réduire pour un
    poste (un guichet partagé, par exemple). Sans choix, 1 jour : le comportement d'avant."""

    JOUR = "jour"
    SEMAINE = "semaine"
    MOIS = "mois"
    DECONNEXION = "deconnexion"  # jusqu'à ce que l'agent se déconnecte (un an au plus, techniquement)
    ORDRE = (JOUR, SEMAINE, MOIS, DECONNEXION)
    CHOIX = [(JOUR, "1 jour"), (SEMAINE, "7 jours"), (MOIS, "30 jours"), (DECONNEXION, "Jusqu'à la déconnexion")]
    DUREES = {
        JOUR: timedelta(days=1),
        SEMAINE: timedelta(days=7),
        MOIS: timedelta(days=30),
        DECONNEXION: timedelta(days=365),
    }
    PAR_DEFAUT = JOUR
    PLAFOND_PAR_DEFAUT = DECONNEXION


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

class RegleInterne(NamedTuple):
    libelle: str
    refus: str  # le message du refus (403) quand la compagnie ne le permet pas
    roles: frozenset  # les postes à qui la règle s'applique ; les autres n'en sont pas affectés
    pole: Role  # le directeur qui la règle (le PDG règle toutes les règles)
    defaut: bool  # le comportement du socle : une compagnie qui ne règle rien le garde


_CHAUFFEURS = frozenset({Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS})

# Règlement intérieur : ce que chaque compagnie permet ou non à certains postes, à sa guise. Chaque règle est vérifiée par le
# serveur (`services.exiger_regle`) au point indiqué ; son défaut est le comportement du socle.
REGLEMENT = {
    "sorties_pieces_corrigeables": RegleInterne(
        libelle="Le magasin et l'atelier corrigent ou annulent une sortie de pièce après coup",
        refus="Le règlement intérieur de la compagnie ne permet pas de corriger ni d'annuler une sortie de pièce.",
        roles=frozenset({Role.MAGASINIER, Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE}),
        pole=Role.DIRECTEUR_TECHNIQUE,
        defaut=True,
    ),
    "mecanicien_confie_ses_ordres": RegleInterne(
        libelle="Le mécanicien confie lui-même son ordre de réparation à un collègue",
        refus=(
            "Le règlement intérieur de la compagnie ne permet pas au mécanicien de confier son ordre à un collègue : "
            "demandez la réaffectation au chef d'atelier ou au directeur technique."
        ),
        roles=frozenset({Role.MECANICIEN}),
        pole=Role.DIRECTEUR_TECHNIQUE,
        defaut=True,
    ),
    "mecanicien_supprime_ses_ordres": RegleInterne(
        libelle="Le mécanicien supprime son ordre de réparation",
        refus="Le règlement intérieur de la compagnie ne permet pas au mécanicien de supprimer un ordre de réparation.",
        roles=frozenset({Role.MECANICIEN}),
        pole=Role.DIRECTEUR_TECHNIQUE,
        defaut=True,
    ),
    "chauffeur_supprime_ses_feuilles": RegleInterne(
        libelle="Le chauffeur supprime sa feuille de route",
        refus="Le règlement intérieur de la compagnie ne permet pas au chauffeur de supprimer sa feuille de route.",
        roles=_CHAUFFEURS,
        pole=Role.DIRECTEUR_EXPLOITATION,
        defaut=True,
    ),
    "drh_gere_les_comptes": RegleInterne(
        libelle="Le DRH crée les comptes du personnel, les modifie et réinitialise leur mot de passe",
        refus="Le règlement intérieur de la compagnie réserve la gestion des comptes au PDG.",
        roles=frozenset({Role.DRH}),
        pole=Role.PDG,
        defaut=False,  # comme avant : seul le PDG intervenait sur les comptes ; le PDG peut confier ce pouvoir au DRH
    ),
    "reparation_leve_le_blocage_qhse": RegleInterne(
        libelle="La réparation terminée remet en service un car bloqué par le QHSE (sinon il attend la levée du QHSE)",
        refus="Le règlement intérieur de la compagnie exige la levée du QHSE : le car reste bloqué jusqu'à ce qu'il la prononce.",
        roles=frozenset({Role.CHEF_ATELIER, Role.MECANICIEN, Role.DIRECTEUR_TECHNIQUE}),
        pole=Role.PDG,
        defaut=True,  # comme avant : clôturer la réparation rend le car disponible
    ),
    "chauffeur_supprime_ses_incidents": RegleInterne(
        libelle="Le chauffeur supprime un incident qu'il a déclaré",
        refus="Le règlement intérieur de la compagnie ne permet pas au chauffeur de supprimer un incident déclaré.",
        roles=_CHAUFFEURS,
        pole=Role.DIRECTEUR_EXPLOITATION,
        defaut=True,
    ),
}


def peut_regler(user, code):
    """Le PDG règle tout le règlement intérieur ; un directeur, les règles de son pôle."""
    if user.company_id is None:
        return False
    return user.role == Role.PDG or user.role == REGLEMENT[code].pole


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
