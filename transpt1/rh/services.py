"""Ce que la RH calcule : l'état des formations obligatoires, l'effet d'un congé sur le personnel disponible, les doléances qui virent
au litige. Hors HTTP, pour servir aussi bien aux vues qu'aux alertes et à la planification des départs."""

import datetime

from django.conf import settings
from django.utils import timezone

from core.models import Role, User
from core.serializers import nom_complet
from rh.models import DemandeConge, Doleance, FormationSuivie, GraviteDoleance, ObligationFormation, StatutConge, StatutDoleance

ROLES_CHAUFFEUR = (Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS)
DUREE_MAX_CONGE_JOURS = 60

# --- Formations obligatoires ------------------------------------------------------------------------------------------------

ORDRE_ETATS = {"expiree": 0, "manquante": 1, "a_renouveler": 2, "a_jour": 3}


def etat_formation(obligation, derniere, aujourdhui):
    """(état, jours restants) d'une obligation pour un agent d'après sa dernière session : `manquante`, `expiree`, `a_renouveler`
    (dans le préavis) ou `a_jour`. Une obligation sans durée de validité, une fois passée, ne s'éteint pas."""
    if derniere is None:
        return "manquante", None
    if derniere.date_expiration is None:
        return "a_jour", None
    jours = (derniere.date_expiration - aujourdhui).days
    if jours < 0:
        return "expiree", jours
    return ("a_renouveler" if jours <= obligation.preavis_jours else "a_jour"), jours


def suivi_formations(company, aujourdhui=None, agent=None):
    """Une ligne par agent actif et par obligation qui concerne son poste, les plus urgentes d'abord."""
    aujourdhui = aujourdhui or timezone.localdate()
    obligations = list(ObligationFormation.objects.filter(company=company))
    agents = User.objects.filter(company=company, is_active=True).order_by("username")
    if agent is not None:
        agents = agents.filter(pk=agent.pk)
    dernieres = {}
    for session in FormationSuivie.objects.filter(company=company).order_by("date_obtention", "id"):
        dernieres[(session.agent_id, session.obligation_id)] = session  # la plus récente écrase les précédentes
    lignes = []
    for membre in agents:
        for obligation in obligations:
            if membre.role not in obligation.roles:
                continue
            derniere = dernieres.get((membre.pk, obligation.pk))
            etat, jours = etat_formation(obligation, derniere, aujourdhui)
            lignes.append(
                {
                    "agent": membre.pk, "agent_nom": nom_complet(membre), "agent_role": membre.role, "obligation": obligation.pk,
                    "obligation_nom": obligation.nom, "etat": etat, "date_obtention": derniere.date_obtention if derniere else None,
                    "date_expiration": derniere.date_expiration if derniere else None, "jours_restants": jours,
                }
            )
    lignes.sort(key=lambda l: (ORDRE_ETATS[l["etat"]], l["jours_restants"] if l["jours_restants"] is not None else 0, l["agent_nom"]))
    return lignes


def resume_formations(lignes):
    return {etat: sum(1 for l in lignes if l["etat"] == etat) for etat in ORDRE_ETATS}


def ajouter_mois(date, mois):
    """La même date `mois` mois plus tard (le dernier jour du mois si celui-ci est plus court)."""
    total = date.month - 1 + mois
    annee, numero = date.year + total // 12, total % 12 + 1
    dernier = (datetime.date(annee + (numero == 12), numero % 12 + 1, 1) - datetime.timedelta(days=1)).day
    return datetime.date(annee, numero, min(date.day, dernier))


# --- Congés ---------------------------------------------------------------------------------------------------------------


def _jours(debut, fin):
    return [debut + datetime.timedelta(days=i) for i in range((fin - debut).days + 1)]


def _roles_equivalents(role):
    """Deux chauffeurs sont interchangeables : leurs congés se comptent ensemble."""
    return ROLES_CHAUFFEUR if role in ROLES_CHAUFFEUR else (role,)


def agents_en_conge(company_id, jour):
    """Les agents dont un congé approuvé couvre ce jour."""
    return set(
        DemandeConge.objects.filter(company_id=company_id, statut=StatutConge.APPROUVE, debut__lte=jour, fin__gte=jour).values_list(
            "agent_id", flat=True
        )
    )


def conge_approuve_de(agent, jour):
    """Le congé approuvé qui couvre ce jour pour cet agent, sinon None."""
    return DemandeConge.objects.filter(agent=agent, statut=StatutConge.APPROUVE, debut__lte=jour, fin__gte=jour).first()


def conge_en_conflit(agent, debut, fin, exclure_id=None):
    """Une autre demande (en attente ou approuvée) du même agent qui chevauche ces dates, sinon None."""
    autres = DemandeConge.objects.filter(
        agent=agent, statut__in=(StatutConge.EN_ATTENTE, StatutConge.APPROUVE), debut__lte=fin, fin__gte=debut
    )
    return autres.exclude(pk=exclure_id).first() if exclure_id else autres.first()


def impact_conge(company, agent, debut, fin, exclure_id=None):
    """Ce que changerait ce congé : jour par jour, combien de collègues du même poste restent disponibles, et pour les conducteurs
    combien de départs sont au programme. Niveaux : `ok`, `tendu` (moins de la moitié de l'équipe, ou juste assez de conducteurs pour
    les départs) et `critique` (plus personne, ou moins de conducteurs que de départs). Estimation : un départ mobilise un conducteur."""
    from billetterie.models import Depart, DepartStatut  # import tardif : billetterie s'appuie sur la RH pour la planification

    roles = _roles_equivalents(agent.role)
    effectif = User.objects.filter(company=company, role__in=roles, is_active=True).count()
    conges = list(
        DemandeConge.objects.filter(
            company=company, statut=StatutConge.APPROUVE, agent__role__in=roles, debut__lte=fin, fin__gte=debut
        )
        .exclude(agent=agent)
        .exclude(pk=exclure_id or 0)
        .select_related("agent")
    )
    conducteur = agent.role in ROLES_CHAUFFEUR
    departs = []
    if conducteur:
        departs = list(
            Depart.objects.filter(company=company, date_heure__date__gte=debut, date_heure__date__lte=fin)
            .exclude(statut=DepartStatut.TERMINE)
            .select_related("ligne")
            .order_by("date_heure")
        )
    jours, pire = [], "ok"
    for jour in _jours(debut, fin):
        en_conge = len({c.agent_id for c in conges if c.debut <= jour <= c.fin})
        restants = effectif - en_conge - 1  # le demandeur lui-même s'absente
        besoin = sum(1 for d in departs if timezone.localtime(d.date_heure).date() == jour) if conducteur else None
        if besoin is not None:
            niveau = "critique" if restants < besoin else "tendu" if restants == besoin and besoin > 0 else "ok"
        else:
            niveau = "critique" if restants <= 0 else "tendu" if restants * 2 < effectif else "ok"
        pire = max(pire, niveau, key=("ok", "tendu", "critique").index)
        jours.append({"date": jour, "en_conge": en_conge, "disponibles_apres": max(restants, 0), "besoin": besoin, "niveau": niveau})
    return {
        "agent": agent.pk, "agent_nom": nom_complet(agent), "role": agent.role, "debut": debut, "fin": fin, "effectif": effectif,
        "niveau": pire, "jours_critiques": sum(1 for j in jours if j["niveau"] == "critique"),
        "jours_tendus": sum(1 for j in jours if j["niveau"] == "tendu"), "jours": jours,
        "collegues_en_conge": [{"agent_nom": nom_complet(c.agent), "debut": c.debut, "fin": c.fin} for c in conges],
        "departs_a_reaffecter": [
            {"id": d.pk, "date_heure": d.date_heure, "ligne": d.ligne.nom}
            for d in departs
            if d.chauffeur_id == agent.pk
        ],
    }


# --- Médiation sociale ----------------------------------------------------------------------------------------------------


def seuil_litige():
    """La gravité à partir de laquelle une doléance est un risque de litige social (`MEDIATION_SEUIL_LITIGE`)."""
    seuil = getattr(settings, "MEDIATION_SEUIL_LITIGE", GraviteDoleance.GRAVE)
    return seuil if seuil in GraviteDoleance.values else GraviteDoleance.GRAVE


def est_litige(doleance):
    """Une doléance encore ouverte dont la gravité atteint le seuil."""
    return (
        doleance.statut not in (StatutDoleance.RESOLUE, StatutDoleance.SANS_SUITE)
        and GraviteDoleance.rang(doleance.gravite) >= GraviteDoleance.rang(seuil_litige())
    )
