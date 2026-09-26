"""Moteur de gamification : points, niveaux, missions du jour, badges, classements.

Le score se recalcule à chaque fois à partir de ce que l'agent a fait (voir `regles`). Seuls sont enregistrés les
événements qui n'arrivent qu'une fois : une mission du jour accomplie, un badge remporté.

Le niveau de gamification configuré pour le poste (voir `configuration`) décide de ce qui est montré : « aucun » rien du tout,
« sobre » points, niveau et missions (ni badges ni classement), « complet » tout. Ne rien montrer, c'est aussi ne rien évaluer.
"""

import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone

from configuration.regles import NiveauGamification
from configuration.services import niveau_gamification
from core.models import Role
from core.serializers import nom_complet
from dashboard.ponctualite import bornes_du_jour
from gamification.models import BadgeObtenu, MissionAccomplie
from gamification.regles import (
    BADGES,
    MISSIONS,
    NOMS_NIVEAUX,
    POINTS_BADGE,
    POINTS_MISSION,
    REGLES,
    SEUILS_NIVEAUX,
)
from gamification.scores import score_gares, score_lignes

# Groupes d'agents que l'on classe entre eux.
GROUPES = {
    "chauffeurs": {Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS},
    "guichetiers": {Role.GUICHETIER},
    "bagagistes": {Role.BAGAGISTE},
    "ateliers": {Role.MECANICIEN, Role.CHEF_ATELIER},
    "controleurs": {Role.CONTROLEUR_LIGNE},
}
TYPES_CLASSEMENT = {
    "gares": "Inter-gares",
    "lignes": "Inter-lignes",
    "chauffeurs": "Inter-chauffeurs",
    "guichetiers": "Inter-guichetiers",
    "bagagistes": "Inter-bagagistes",
    "ateliers": "Inter-ateliers",
    "controleurs": "Inter-contrôleurs",
}
# Ce que chaque poste peut consulter en plus du classement des gares : son propre groupe ; la direction voit tout.
GROUPE_DU_ROLE = {
    Role.CHAUFFEUR_PRINCIPAL: "chauffeurs", Role.CHAUFFEUR_RELAIS: "chauffeurs", Role.GUICHETIER: "guichetiers",
    Role.BAGAGISTE: "bagagistes", Role.MECANICIEN: "ateliers", Role.CHEF_ATELIER: "ateliers",
    Role.CONTROLEUR_LIGNE: "controleurs",
}
ROLES_VUE_D_ENSEMBLE = {
    Role.PDG, Role.SECRETAIRE_GENERAL, Role.DIRECTEUR_EXPLOITATION, Role.QHSE, Role.DIRECTEUR_TECHNIQUE, Role.DRH,
}
PERIODES = ("jour", "semaine", "mois", "tout")


def bornes_de_periode(periode, maintenant):
    """[debut, fin) d'une période ; `None` pour une borne ouverte."""
    debut_jour, fin_jour = bornes_du_jour(maintenant)
    if periode == "jour":
        return debut_jour, fin_jour
    if periode == "semaine":
        return fin_jour - datetime.timedelta(days=7), fin_jour
    if periode == "mois":
        return debut_jour.replace(day=1), fin_jour
    return None, None


# --- Points et niveaux -----------------------------------------------------------------------------------------------


def niveau_pour(points):
    """Le niveau d'un total de points : numéro, nom, et progression vers le suivant. Après le dernier seuil, un niveau de
    plus tous les 1 000 points."""
    points = max(0, points)
    if points >= SEUILS_NIVEAUX[-1]:
        en_plus = (points - SEUILS_NIVEAUX[-1]) // 1000
        numero = len(SEUILS_NIVEAUX) + en_plus
        plancher = SEUILS_NIVEAUX[-1] + en_plus * 1000
        suivant = plancher + 1000
    else:
        indice = max(i for i, seuil in enumerate(SEUILS_NIVEAUX) if points >= seuil)
        numero, plancher, suivant = indice + 1, SEUILS_NIVEAUX[indice], SEUILS_NIVEAUX[indice + 1]
    return {
        "numero": numero,
        "nom": NOMS_NIVEAUX[min(numero, len(NOMS_NIVEAUX)) - 1],
        "points_du_niveau": plancher,
        "points_niveau_suivant": suivant,
        "progression_pourcent": min(100, round(100 * (points - plancher) / (suivant - plancher))),
    }


def points_agent(agent, debut=None, fin=None):
    """Points d'un agent sur une période (toute sa carrière par défaut) : règles du poste, missions et badges."""
    detail = []
    total = 0
    for regle in REGLES.get(agent.role, []):
        nombre = regle.compteur(agent, debut, fin)
        if nombre:
            detail.append({"code": regle.code, "libelle": regle.libelle, "nombre": nombre, "points": nombre * regle.points})
            total += nombre * regle.points
    missions = MissionAccomplie.objects.filter(agent=agent)
    badges = BadgeObtenu.objects.filter(agent=agent)
    if debut is not None:
        missions, badges = missions.filter(accomplie_le__gte=debut), badges.filter(obtenu_le__gte=debut)
    if fin is not None:
        missions, badges = missions.filter(accomplie_le__lt=fin), badges.filter(obtenu_le__lt=fin)
    nb_missions, nb_badges = missions.count(), badges.count()
    if nb_missions:
        detail.append({"code": "missions", "libelle": "Missions du jour accomplies", "nombre": nb_missions, "points": nb_missions * POINTS_MISSION})
        total += nb_missions * POINTS_MISSION
    if nb_badges:
        detail.append({"code": "badges", "libelle": "Badges remportés", "nombre": nb_badges, "points": nb_badges * POINTS_BADGE})
        total += nb_badges * POINTS_BADGE
    return {"total": total, "detail": detail}


# --- Missions du jour et badges ---------------------------------------------------------------------------------------


def missions_du_jour(agent, maintenant, enregistrer=True):
    """Les missions du jour de l'agent avec leur progression. Une mission accomplie est enregistrée une fois (elle rapporte
    des points) ; renvoie `(missions, nouvelles)` où `nouvelles` sont celles qui viennent d'être accomplies."""
    debut, fin = bornes_du_jour(maintenant)
    jour = timezone.localdate(maintenant)
    deja = set(MissionAccomplie.objects.filter(agent=agent, date=jour).values_list("code", flat=True))
    missions, nouvelles = [], []
    for mission in MISSIONS.get(agent.role, []):
        progres = mission.progression(agent, debut, fin)
        accomplie = progres >= mission.objectif or mission.code in deja
        if accomplie and enregistrer and mission.code not in deja:
            _, creee = MissionAccomplie.objects.get_or_create(
                agent=agent, code=mission.code, date=jour, defaults={"company_id": agent.company_id}
            )
            if creee:
                nouvelles.append({"code": mission.code, "libelle": mission.libelle, "points": POINTS_MISSION})
        missions.append(
            {
                "code": mission.code,
                "libelle": mission.libelle,
                "objectif": mission.objectif,
                "progres": min(progres, mission.objectif),
                "accomplie": accomplie,
                "points": POINTS_MISSION,
            }
        )
    return missions, nouvelles


def badges_de(agent, maintenant, enregistrer=True):
    """Badges de l'agent : remportés (avec la date), à gagner (avec leur description), et ceux qui viennent d'être remportés."""
    nouveaux = []
    if enregistrer:
        for badge in BADGES:
            if agent.role not in badge.roles:
                continue
            periode = badge.condition(agent, maintenant)
            if periode is None:
                continue
            _, cree = BadgeObtenu.objects.get_or_create(
                agent=agent, code=badge.code, periode=periode, defaults={"company_id": agent.company_id}
            )
            if cree:
                nouveaux.append({"code": badge.code, "libelle": badge.libelle, "points": POINTS_BADGE})
    obtenus = {}
    for obtenu in BadgeObtenu.objects.filter(agent=agent).order_by("obtenu_le"):
        obtenus.setdefault(obtenu.code, []).append(obtenu)
    catalogue = []
    for badge in BADGES:
        if agent.role not in badge.roles:
            continue
        gagnes = obtenus.get(badge.code, [])
        catalogue.append(
            {
                "code": badge.code,
                "libelle": badge.libelle,
                "description": badge.description,
                "obtenu": bool(gagnes),
                "fois": len(gagnes),
                "derniere_periode": gagnes[-1].periode if gagnes else None,
                "obtenu_le": gagnes[-1].obtenu_le if gagnes else None,
            }
        )
    return catalogue, nouveaux


def types_de_classement(agent):
    """Les classements que cet agent peut consulter."""
    types = ["gares"]
    if agent.role in ROLES_VUE_D_ENSEMBLE:
        types += [t for t in TYPES_CLASSEMENT if t != "gares"]
    else:
        if agent.role == Role.CHEF_LIGNE:
            types.append("lignes")
        if agent.role in GROUPE_DU_ROLE:
            types.append(GROUPE_DU_ROLE[agent.role])
    return [{"type": t, "libelle": TYPES_CLASSEMENT[t]} for t in types]


def etat_agent(agent, maintenant=None, enregistrer=True):
    """Tout ce que le jeu montre à un agent : niveau, points, missions du jour, badges, et ce qu'il vient de gagner."""
    maintenant = maintenant or timezone.now()
    niveau_config = niveau_gamification(agent)
    if agent.company_id is None or niveau_config == NiveauGamification.AUCUN:
        return {"actif": False, "niveau_gamification": niveau_config}

    missions, missions_nouvelles = missions_du_jour(agent, maintenant, enregistrer)
    complet = niveau_config == NiveauGamification.COMPLET
    badges, badges_nouveaux = badges_de(agent, maintenant, enregistrer) if complet else ([], [])
    points = points_agent(agent)
    debut_mois, fin_mois = bornes_de_periode("mois", maintenant)
    return {
        "actif": True,
        "niveau_gamification": niveau_config,
        # Vrai si le poste a quelque chose à marquer (règles de points, missions) : sinon, pas de « niveau 1, 0 point » à afficher.
        "score_applicable": bool(REGLES.get(agent.role) or MISSIONS.get(agent.role)),
        "points": max(0, points["total"]),
        "points_detail": points["detail"],
        "points_du_mois": max(0, points_agent(agent, debut_mois, fin_mois)["total"]),
        "niveau": niveau_pour(points["total"]),
        "missions": missions,
        "badges": badges,
        "classements": types_de_classement(agent) if complet else [],
        "nouvelles": {"missions": missions_nouvelles, "badges": badges_nouveaux},
    }


# --- Classements ------------------------------------------------------------------------------------------------------


def classement(agent, type_classement, periode, maintenant=None):
    """Classement d'un type sur une période. Les agents dont le poste n'affiche pas la gamification n'y figurent pas."""
    maintenant = maintenant or timezone.now()
    debut, fin = bornes_de_periode(periode, maintenant)
    if type_classement in ("gares", "lignes"):
        # Un score de gare ou de ligne porte sur une période bornée : « tout » vaut « mois » (il faut un début).
        debut, fin = (debut, fin) if debut is not None else bornes_de_periode("mois", maintenant)
        calcul = score_gares if type_classement == "gares" else score_lignes
        return calcul(agent.company_id, debut, fin, maintenant)

    lignes = []
    for candidat in get_user_model().objects.filter(company_id=agent.company_id, role__in=GROUPES[type_classement]):
        if niveau_gamification(candidat) != NiveauGamification.COMPLET:
            continue
        lignes.append(
            {"id": candidat.id, "nom": nom_complet(candidat), "role": candidat.role, "score": points_agent(candidat, debut, fin)["total"]}
        )
    lignes.sort(key=lambda ligne: (-ligne["score"], ligne["nom"]))
    rang, precedent = 0, None
    for index, ligne in enumerate(lignes, start=1):
        if ligne["score"] != precedent:
            rang, precedent = index, ligne["score"]
        ligne["rang"] = rang
        ligne["moi"] = ligne["id"] == agent.id
    return lignes


def vue_des_agents(company_id):
    """Les scores de tous les agents (aide à l'évaluation du DRH), sauf ceux dont le poste n'affiche pas la gamification."""
    lignes = []
    for agent in get_user_model().objects.filter(company_id=company_id).exclude(role=Role.SUPERADMIN).order_by("username"):
        if niveau_gamification(agent) == NiveauGamification.AUCUN:
            continue
        points = points_agent(agent)["total"]
        lignes.append(
            {
                "id": agent.id,
                "nom": nom_complet(agent),
                "role": agent.role,
                "points": max(0, points),
                "niveau": niveau_pour(points),
                "badges": BadgeObtenu.objects.filter(agent=agent).count(),
                "missions_accomplies": MissionAccomplie.objects.filter(agent=agent).count(),
            }
        )
    lignes.sort(key=lambda ligne: (-ligne["points"], ligne["nom"]))
    return lignes
