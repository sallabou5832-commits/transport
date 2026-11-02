"""Configuration effective d'un agent : le défaut du socle, réglé par son poste, puis par lui-même, sans jamais
dépasser le cadre fixé par la compagnie."""

from rest_framework.exceptions import PermissionDenied

from configuration import regles
from configuration.models import ConfigurationAgent, ConfigurationCompagnie, ConfigurationPoste, ReglementInterieur
from configuration.regles import AisanceNumerique, NiveauAutomatisation, NiveauGamification


def cadre_de(company_id):
    """Les plafonds de la compagnie : (automatisation_max, gamification_max)."""
    cadre = ConfigurationCompagnie.objects.filter(company_id=company_id).first()
    if cadre is None:
        return NiveauAutomatisation.AUTOMATIQUE, NiveauGamification.COMPLET
    return cadre.automatisation_max, cadre.gamification_max


def configuration_effective(user):
    """Ce qui s'applique réellement à cet agent : niveau d'automatisation, niveau de gamification, fonctions retirées,
    préférence vocale, aisance numérique."""
    if user.company_id is None:  # l'opérateur de la plateforme : pas de poste, pas de jeu
        return {
            "niveau_automatisation": regles.AUTOMATISATION_PAR_DEFAUT,
            "niveau_gamification": NiveauGamification.AUCUN,
            "fonctions_desactivees": [],
            "prefere_vocal": False,
            "aisance_numerique": AisanceNumerique.MOYENNE,
        }
    automatisation_max, gamification_max = cadre_de(user.company_id)
    poste = ConfigurationPoste.objects.filter(company_id=user.company_id, role=user.role).first()
    agent = ConfigurationAgent.objects.filter(agent=user).first()

    def choisir(champ, defaut):
        for source in (agent, poste):
            valeur = getattr(source, champ, None) if source is not None else None
            if valeur:
                return valeur
        return defaut

    automatisation = choisir("niveau_automatisation", regles.AUTOMATISATION_PAR_DEFAUT)
    gamification = choisir("niveau_gamification", regles.gamification_par_defaut(user.role))
    fonctions = set(poste.fonctions_desactivees if poste else []) | set(agent.fonctions_desactivees if agent else [])
    if agent is not None and agent.prefere_vocal is not None:
        vocal = agent.prefere_vocal
    else:
        vocal = poste.prefere_vocal if poste else False
    return {
        "niveau_automatisation": regles.plafonner(automatisation, automatisation_max, NiveauAutomatisation.ORDRE),
        "niveau_gamification": regles.plafonner(gamification, gamification_max, NiveauGamification.ORDRE),
        "fonctions_desactivees": sorted(fonctions),
        "prefere_vocal": vocal,
        "aisance_numerique": agent.aisance_numerique if agent else AisanceNumerique.MOYENNE,
    }


def niveau_automatisation(user):
    return configuration_effective(user)["niveau_automatisation"]


def niveau_gamification(user):
    return configuration_effective(user)["niveau_gamification"]


def automatisation_au_moins(user, niveau):
    actuel = niveau_automatisation(user)
    return NiveauAutomatisation.ORDRE.index(actuel) >= NiveauAutomatisation.ORDRE.index(niveau)


def fonction_active(user, code):
    return code not in configuration_effective(user)["fonctions_desactivees"]


def exiger_fonction(user, code):
    """Refuse (403) si un échelon supérieur a retiré cette fonction au poste ou à l'agent."""
    if not fonction_active(user, code):
        raise PermissionDenied(f"Cette fonction est désactivée pour votre poste : {regles.FONCTIONS[code].lower()}.")


def reglement_de(company_id):
    """Le règlement intérieur de la compagnie, {code: permis} : le défaut du socle pour les règles qu'elle n'a pas réglées."""
    valeurs = {code: regle.defaut for code, regle in regles.REGLEMENT.items()}
    reglement = ReglementInterieur.objects.filter(company_id=company_id).first() if company_id is not None else None
    if reglement is not None:
        valeurs.update({code: permis for code, permis in reglement.regles.items() if code in valeurs})
    return valeurs


def exiger_regle(user, code):
    """Refuse (403) si le règlement intérieur de la compagnie ne permet pas `code` au poste de l'utilisateur."""
    regle = regles.REGLEMENT[code]
    if user.role in regle.roles and not reglement_de(user.company_id)[code]:
        raise PermissionDenied(regle.refus)
