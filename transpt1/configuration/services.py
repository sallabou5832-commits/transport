"""Configuration effective d'un agent : le défaut du socle, réglé par son poste, puis par lui-même, sans jamais
dépasser le cadre fixé par la compagnie."""

from rest_framework.exceptions import PermissionDenied

from configuration import regles
from configuration.models import (
    ConfigurationAgent,
    ConfigurationCompagnie,
    ConfigurationPoste,
    PreferencePersonnelle,
    ReglementInterieur,
)
from configuration.regles import AisanceNumerique, DureeSession, NiveauAutomatisation, NiveauGamification


def cadre_de(company_id):
    """Les plafonds de la compagnie : (automatisation_max, gamification_max)."""
    cadre = ConfigurationCompagnie.objects.filter(company_id=company_id).first()
    if cadre is None:
        return NiveauAutomatisation.AUTOMATIQUE, NiveauGamification.COMPLET
    return cadre.automatisation_max, cadre.gamification_max


def politique_session(user):
    """Ce que la compagnie permet pour les sessions de cet agent : `duree_max`, la plus longue session (plafond de la
    compagnie, réduit éventuellement pour son poste), et `code_court_exige` sur le mobile. Rien de réglé : jusqu'à la
    déconnexion, code court facultatif."""
    if user.company_id is None:  # l'opérateur de la plateforme
        return {"duree_max": DureeSession.PLAFOND_PAR_DEFAUT, "code_court_exige": False}
    cadre = ConfigurationCompagnie.objects.filter(company_id=user.company_id).first()
    plafond = cadre.duree_session_max if cadre is not None else DureeSession.PLAFOND_PAR_DEFAUT
    reduit = (
        ConfigurationPoste.objects.filter(company_id=user.company_id, role=user.role)
        .values_list("duree_session_max", flat=True)
        .first()
    )
    if reduit:
        plafond = regles.plafonner(reduit, plafond, DureeSession.ORDRE)
    return {"duree_max": plafond, "code_court_exige": bool(cadre is not None and cadre.code_court_exige)}


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
    personnelle = PreferencePersonnelle.objects.filter(agent=user).values_list("prefere_vocal", flat=True).first()
    if personnelle is not None and not vocal_impose(poste, agent):
        vocal = personnelle  # le choix de l'agent, que son supérieur n'a pas imposé
    elif agent is not None and agent.prefere_vocal is not None:
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


def vocal_impose(poste, agent):
    """Le supérieur a imposé le mode vocal, pour le poste ou pour cet agent : l'agent ne le choisit pas lui-même."""
    return bool((poste is not None and poste.prefere_vocal_impose) or (agent is not None and agent.prefere_vocal_impose))


def vocal_impose_pour(user):
    if user.company_id is None:
        return False
    poste = ConfigurationPoste.objects.filter(company_id=user.company_id, role=user.role).first()
    agent = ConfigurationAgent.objects.filter(agent=user).first()
    return vocal_impose(poste, agent)


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
