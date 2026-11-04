"""Ce que le jeu récompense, poste par poste : règles de points, missions du jour, badges.

Tout est calculé sur ce que l'agent a réellement fait (tickets vendus, trajets, colis, interventions, incidents traités...),
jamais sur une saisie : annuler un billet retire donc des points tout seul. Un ton sérieux : des objectifs de travail
bien fait (zéro erreur, ponctualité, sécurité), pas des points pour le plaisir de cliquer.
"""

import datetime
from dataclasses import dataclass
from typing import Callable

from django.db.models import Count, F, Q
from django.utils import timezone

from audit.models import JournalAudit
from billetterie.models import ClotureCaisse, StatutTicket, Ticket
from colis.models import Colis
from core.models import Role
from dashboard.ponctualite import TOLERANCE_RETARD
from maintenance.models import OrdreReparation, Piece, StatutOrdreReparation
from personnel_roulant.models import (
    BlocageSecurite,
    ControleLigne,
    FeuilleDeRoute,
    Incident,
    StatutIncident,
    VerificationTicket,
)
from reseau.models import Gare

POINTS_MISSION = 10  # bonus pour une mission du jour accomplie
POINTS_BADGE = 25  # bonus pour un badge remporté

# Niveaux : seuils de points cumulés. Au-delà du dernier, un niveau de plus tous les 1 000 points.
SEUILS_NIVEAUX = [0, 50, 150, 300, 500, 800, 1200, 1800, 2600, 3600]
NOMS_NIVEAUX = ["Recrue", "Apprenti", "Confirmé", "Habile", "Expert", "Maître", "Vétéran", "Champion", "Légende", "Icône"]


# --- Compteurs : combien de fois l'agent l'a fait dans [debut, fin) (une borne à None = ouverte) ------------------------


def _dans(queryset, champ, debut, fin):
    if debut is not None:
        queryset = queryset.filter(**{f"{champ}__gte": debut})
    if fin is not None:
        queryset = queryset.filter(**{f"{champ}__lt": fin})
    return queryset


def tickets_vendus(agent, debut, fin):
    return _dans(Ticket.objects.filter(vendu_par=agent, statut=StatutTicket.VALIDE), "date_vente", debut, fin).count()


def tickets_annules(agent, debut, fin):
    return _dans(Ticket.objects.filter(vendu_par=agent, statut=StatutTicket.ANNULE), "date_vente", debut, fin).count()


def _feuilles_terminees(agent, debut, fin):
    return _dans(
        FeuilleDeRoute.objects.filter(
            chauffeur=agent, heure_depart_reelle__isnull=False, heure_arrivee_reelle__isnull=False
        ),
        "heure_depart_prevue", debut, fin,
    )


def trajets_a_l_heure(agent, debut, fin):
    return _feuilles_terminees(agent, debut, fin).filter(
        heure_depart_reelle__lte=F("heure_depart_prevue") + TOLERANCE_RETARD
    ).count()


def trajets_en_retard(agent, debut, fin):
    return _feuilles_terminees(agent, debut, fin).filter(
        heure_depart_reelle__gt=F("heure_depart_prevue") + TOLERANCE_RETARD
    ).count()


def trajets_sans_incident(agent, debut, fin):
    return _feuilles_terminees(agent, debut, fin).annotate(n=Count("incidents")).filter(n=0).count()


def checklists_faites(agent, debut, fin):
    return _dans(
        FeuilleDeRoute.objects.filter(chauffeur=agent).annotate(n=Count("checklist_items")).filter(n__gt=0),
        "heure_depart_prevue", debut, fin,
    ).count()


def colis_enregistres(agent, debut, fin):
    return _dans(Colis.objects.filter(enregistre_par=agent), "enregistre_le", debut, fin).count()


def colis_charges(agent, debut, fin):
    return _dans(Colis.objects.filter(charge_par=agent), "charge_le", debut, fin).count()


def colis_remis(agent, debut, fin):
    return _dans(Colis.objects.filter(retire_par=agent), "retire_le", debut, fin).count()


def colis_annules(agent, debut, fin):
    """Enregistrements de cet agent qui ont dû être annulés : une erreur de colis."""
    return _dans(Colis.objects.filter(enregistre_par=agent, annule_le__isnull=False), "annule_le", debut, fin).count()


def ordres_clotures(agent, debut, fin):
    return _dans(
        OrdreReparation.objects.filter(mecanicien=agent, statut=StatutOrdreReparation.TERMINE), "date_cloture", debut, fin
    ).count()


def blocages_poses(agent, debut, fin):
    return _dans(BlocageSecurite.objects.filter(pose_par=agent), "pose_le", debut, fin).count()


def _audit(agent, debut, fin, **filtres):
    """Actions de l'agent relevées dans le journal d'audit (il sait qui a fait quoi, y compris quand le modèle ne le dit pas)."""
    return _dans(JournalAudit.objects.filter(acteur=agent, **filtres), "date", debut, fin).count()


def sorties_enregistrees(agent, debut, fin):
    return _audit(agent, debut, fin, objet_type="maintenance.sortiepiece", action="creation")


def ordres_ouverts(agent, debut, fin):
    return _audit(agent, debut, fin, objet_type="maintenance.ordrereparation", action="creation")


def incidents_traites(agent, debut, fin):
    return _audit(
        agent, debut, fin, objet_type="personnel_roulant.incident", action="modification", changements__statut__1="traite"
    )


def dossiers_traites(agent, debut, fin):
    return _audit(agent, debut, fin, objet_type="supports.dossieragent", action__in=["creation", "modification"])


def sinistres_clos(agent, debut, fin):
    return _audit(agent, debut, fin, objet_type="supports.sinistre", action="modification", changements__statut__1="clos")


def departs_planifies(agent, debut, fin):
    return _audit(agent, debut, fin, objet_type="billetterie.depart", action="creation")


def reaffectations(agent, debut, fin):
    return _dans(
        JournalAudit.objects.filter(acteur=agent, objet_type="billetterie.depart", action="modification").filter(
            # Le journal nomme les champs par leur attribut : chauffeur_id, vehicule_id.
            Q(changements__has_key="chauffeur_id") | Q(changements__has_key="vehicule_id")
        ),
        "date", debut, fin,
    ).count()


def _feuilles_de_sa_gare(chef, debut, fin):
    return _dans(
        FeuilleDeRoute.objects.filter(depart__ligne__gare_depart__chef=chef, heure_depart_reelle__isnull=False),
        "heure_depart_prevue", debut, fin,
    )


def departs_de_sa_gare_a_l_heure(chef, debut, fin):
    return _feuilles_de_sa_gare(chef, debut, fin).filter(
        heure_depart_reelle__lte=F("heure_depart_prevue") + TOLERANCE_RETARD
    ).count()


def departs_de_sa_gare_en_retard(chef, debut, fin):
    return _feuilles_de_sa_gare(chef, debut, fin).filter(
        heure_depart_reelle__gt=F("heure_depart_prevue") + TOLERANCE_RETARD
    ).count()


def controles_clotures(controleur, debut, fin):
    return _dans(ControleLigne.objects.filter(controleur=controleur, cloture_le__isnull=False), "cloture_le", debut, fin).count()


def billets_verifies(controleur, debut, fin):
    return _dans(VerificationTicket.objects.filter(controle__controleur=controleur), "verifie_le", debut, fin).count()


def infractions_signalees(controleur, debut, fin):
    return _dans(
        ControleLigne.objects.filter(controleur=controleur, cloture_le__isnull=False, infraction_grave=True), "cloture_le", debut, fin
    ).count()


def caisses_cloturees(chef, debut, fin):
    return _dans(ClotureCaisse.objects.filter(gare__chef=chef), "cloture_le", debut, fin).count()


# --- Règles de points, missions, badges ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Regle:
    code: str
    libelle: str
    points: int
    compteur: Callable


@dataclass(frozen=True)
class Mission:
    code: str
    libelle: str
    objectif: int
    progression: Callable  # (agent, debut, fin) -> int, sur la journée


@dataclass(frozen=True)
class Badge:
    code: str
    libelle: str
    description: str
    roles: frozenset
    # (agent, maintenant) -> période (« » pour un badge qu'on n'a qu'une fois) si mérité, sinon None
    condition: Callable


CHAUFFEURS = (Role.CHAUFFEUR_PRINCIPAL, Role.CHAUFFEUR_RELAIS)


def _regles_chauffeur():
    return [
        Regle("trajet_a_l_heure", "Trajet parti à l'heure", 10, trajets_a_l_heure),
        Regle("trajet_en_retard", "Trajet parti en retard", -3, trajets_en_retard),
        Regle("trajet_sans_incident", "Trajet sans incident", 5, trajets_sans_incident),
        Regle("checklist_faite", "Checklist avant départ faite", 3, checklists_faites),
    ]


REGLES = {
    Role.GUICHETIER: [
        Regle("ticket_vendu", "Ticket vendu", 1, tickets_vendus),
        Regle("ticket_annule", "Erreur de billetterie (ticket annulé)", -5, tickets_annules),
    ],
    Role.BAGAGISTE: [
        Regle("colis_enregistre", "Colis enregistré", 2, colis_enregistres),
        Regle("colis_charge", "Colis chargé", 1, colis_charges),
        Regle("colis_remis", "Colis remis au client", 3, colis_remis),
        Regle("colis_annule", "Erreur de colis (enregistrement annulé)", -5, colis_annules),
    ],
    Role.CHAUFFEUR_PRINCIPAL: _regles_chauffeur(),
    Role.CHAUFFEUR_RELAIS: _regles_chauffeur(),
    Role.MECANICIEN: [Regle("intervention_cloturee", "Intervention clôturée", 10, ordres_clotures)],
    Role.CHEF_ATELIER: [
        Regle("intervention_cloturee", "Intervention clôturée", 10, ordres_clotures),
        Regle("ordre_ouvert", "Ordre de réparation ouvert", 1, ordres_ouverts),
    ],
    Role.DIRECTEUR_TECHNIQUE: [Regle("ordre_ouvert", "Ordre de réparation ouvert", 1, ordres_ouverts)],
    Role.MAGASINIER: [Regle("sortie_enregistree", "Sortie de pièce enregistrée", 2, sorties_enregistrees)],
    Role.QHSE: [
        Regle("incident_traite", "Incident traité", 5, incidents_traites),
        Regle("blocage_pose", "Départ bloqué pour sécurité", 3, blocages_poses),
    ],
    Role.CHEF_GARE: [
        Regle("depart_a_l_heure", "Départ de sa gare à l'heure", 2, departs_de_sa_gare_a_l_heure),
        Regle("depart_en_retard", "Départ de sa gare en retard", -1, departs_de_sa_gare_en_retard),
        Regle("caisse_cloturee", "Caisse de l'équipe clôturée", 2, caisses_cloturees),
    ],
    Role.CHEF_LIGNE: [
        Regle("depart_planifie", "Départ planifié", 2, departs_planifies),
        Regle("reaffectation", "Réaffectation d'un imprévu", 3, reaffectations),
    ],
    Role.CONTROLEUR_LIGNE: [
        Regle("controle_cloture", "Contrôle clôturé", 5, controles_clotures),
        Regle("billet_verifie", "Billet vérifié", 1, billets_verifies),
        Regle("infraction_signalee", "Infraction grave signalée", 10, infractions_signalees),
    ],
    Role.DRH: [Regle("dossier_traite", "Dossier agent traité", 2, dossiers_traites)],
    Role.RESPONSABLE_JURIDIQUE: [Regle("sinistre_clos", "Sinistre clos", 5, sinistres_clos)],
}


def _zero_retard(agent, debut, fin):
    return 1 if trajets_a_l_heure(agent, debut, fin) >= 1 and trajets_en_retard(agent, debut, fin) == 0 else 0


def _zero_erreur_billetterie(agent, debut, fin):
    return tickets_vendus(agent, debut, fin) if tickets_annules(agent, debut, fin) == 0 else 0


def _zero_rupture(agent, debut, fin):
    return 0 if Piece.objects.filter(company_id=agent.company_id, quantite_stock=0).exists() else 1


def _zero_incident_en_retard(agent, debut, fin):
    """Cahier des charges (QHSE) : « zéro incident non traité à temps » — aucun incident ouvert depuis plus de 24 h."""
    limite = timezone.now() - datetime.timedelta(hours=24)
    en_retard = Incident.objects.filter(company_id=agent.company_id, statut=StatutIncident.OUVERT, date__lt=limite)
    return 0 if en_retard.exists() else 1


def _gare_sans_retard(chef, debut, fin):
    return 1 if departs_de_sa_gare_a_l_heure(chef, debut, fin) >= 1 and departs_de_sa_gare_en_retard(chef, debut, fin) == 0 else 0


MISSIONS = {
    Role.GUICHETIER: [
        Mission("zero_erreur", "Zéro erreur de billetterie : 5 tickets sans annulation", 5, _zero_erreur_billetterie),
        Mission("vendre_20", "Vendre 20 tickets", 20, tickets_vendus),
    ],
    Role.BAGAGISTE: [
        Mission("enregistrer_5", "Enregistrer 5 colis", 5, colis_enregistres),
        Mission("remettre_3", "Remettre 3 colis à leurs destinataires", 3, colis_remis),
    ],
    Role.CHAUFFEUR_PRINCIPAL: [
        Mission("zero_retard", "Zéro retard sur le trajet", 1, _zero_retard),
        Mission("checklist", "Faire sa checklist avant départ", 1, checklists_faites),
    ],
    Role.CHAUFFEUR_RELAIS: [
        Mission("zero_retard", "Zéro retard sur le trajet", 1, _zero_retard),
        Mission("checklist", "Faire sa checklist avant départ", 1, checklists_faites),
    ],
    Role.MECANICIEN: [Mission("cloturer_3", "Clôturer 3 interventions", 3, ordres_clotures)],
    Role.CHEF_ATELIER: [Mission("cloturer_3", "Clôturer 3 interventions", 3, ordres_clotures)],
    Role.MAGASINIER: [
        Mission("sorties_5", "Enregistrer 5 sorties de pièces", 5, sorties_enregistrees),
        Mission("zero_rupture", "Zéro rupture de stock", 1, _zero_rupture),
    ],
    Role.QHSE: [
        Mission("traiter_3", "Traiter 3 incidents", 3, incidents_traites),
        Mission("zero_incident_en_retard", "Zéro incident non traité à temps", 1, _zero_incident_en_retard),
    ],
    Role.CHEF_GARE: [Mission("gare_sans_retard", "Journée sans retard sur sa gare", 1, _gare_sans_retard)],
    Role.CHEF_LIGNE: [Mission("planifier_3", "Planifier 3 départs", 3, departs_planifies)],
    Role.CONTROLEUR_LIGNE: [
        Mission("controler_2", "Contrôler 2 trajets", 2, controles_clotures),
        Mission("verifier_20", "Vérifier 20 billets", 20, billets_verifies),
    ],
    Role.DRH: [Mission("dossiers_3", "Traiter 3 dossiers d'agents", 3, dossiers_traites)],
    Role.RESPONSABLE_JURIDIQUE: [Mission("sinistre_1", "Clore un sinistre", 1, sinistres_clos)],
}


# --- Badges -------------------------------------------------------------------------------------------------------


def _une_fois(test):
    return lambda agent, maintenant: "" if test(agent, maintenant) else None


def _six_mois_sans_retard(agent, maintenant):
    debut = maintenant - datetime.timedelta(days=180)
    return trajets_a_l_heure(agent, debut, maintenant) >= 20 and trajets_en_retard(agent, debut, maintenant) == 0


def _gare_du_mois(chef, maintenant):
    """Meilleure gare du mois écoulé : le badge va au chef de la gare classée première (avec de l'activité). La période
    (« 2026-08 ») fait qu'il se regagne chaque mois."""
    from gamification.scores import score_gares

    debut_courant = timezone.localtime(maintenant).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    debut = (debut_courant - datetime.timedelta(days=1)).replace(day=1)
    premieres = {
        ligne["id"] for ligne in score_gares(chef.company_id, debut, debut_courant, maintenant) if ligne["rang"] == 1 and ligne["score"] > 0
    }
    sa_gare = set(Gare.objects.filter(chef=chef).values_list("id", flat=True))
    return f"{debut:%Y-%m}" if premieres & sa_gare else None


BADGES = [
    Badge("premiere_vente", "Première vente", "Premier ticket vendu.", frozenset({Role.GUICHETIER}),
          _une_fois(lambda a, m: tickets_vendus(a, None, None) >= 1)),
    Badge("centurion", "Centurion", "100 tickets vendus.", frozenset({Role.GUICHETIER}),
          _une_fois(lambda a, m: tickets_vendus(a, None, None) >= 100)),
    Badge("caisse_juste", "Caisse juste", "30 tickets vendus en 7 jours sans une seule annulation.",
          frozenset({Role.GUICHETIER}),
          # Fenêtre ouverte vers le présent : un ticket vendu à l'instant même du calcul compte (horloge à paliers).
          _une_fois(lambda a, m: tickets_vendus(a, m - datetime.timedelta(days=7), None) >= 30
                    and tickets_annules(a, m - datetime.timedelta(days=7), None) == 0)),
    Badge("routier_regulier", "Routier régulier", "10 trajets sans incident.", frozenset(CHAUFFEURS),
          _une_fois(lambda a, m: trajets_sans_incident(a, None, None) >= 10)),
    Badge("routier_exemplaire", "Routier exemplaire", "100 trajets sans incident.", frozenset(CHAUFFEURS),
          _une_fois(lambda a, m: trajets_sans_incident(a, None, None) >= 100)),
    Badge("six_mois_sans_retard", "Six mois sans retard", "Au moins 20 trajets en 6 mois, aucun parti en retard.",
          frozenset(CHAUFFEURS), _une_fois(_six_mois_sans_retard)),
    Badge("bagagiste_soigneux", "Bagagiste soigneux", "25 colis remis sans une erreur d'enregistrement.",
          frozenset({Role.BAGAGISTE}),
          _une_fois(lambda a, m: colis_remis(a, None, None) >= 25 and colis_annules(a, None, None) == 0)),
    Badge("vigie_securite", "Vigie sécurité", "10 incidents traités.", frozenset({Role.QHSE}),
          _une_fois(lambda a, m: incidents_traites(a, None, None) >= 10)),
    Badge("atelier_au_top", "Atelier au top", "10 interventions clôturées.", frozenset({Role.MECANICIEN, Role.CHEF_ATELIER}),
          _une_fois(lambda a, m: ordres_clotures(a, None, None) >= 10)),
    Badge("dossier_clos", "Dossier clos", "10 dossiers traités.", frozenset({Role.DRH, Role.RESPONSABLE_JURIDIQUE}),
          _une_fois(lambda a, m: dossiers_traites(a, None, None) + sinistres_clos(a, None, None) >= 10)),
    Badge("controleur_vigilant", "Contrôleur vigilant", "25 contrôles clôturés.", frozenset({Role.CONTROLEUR_LIGNE}),
          _une_fois(lambda a, m: controles_clotures(a, None, None) >= 25)),
    Badge("regulateur_reactif", "Régulateur réactif", "10 imprévus réaffectés.", frozenset({Role.CHEF_LIGNE}),
          _une_fois(lambda a, m: reaffectations(a, None, None) >= 10)),
    Badge("gare_du_mois", "Gare du mois", "Chef de la meilleure gare du mois écoulé.", frozenset({Role.CHEF_GARE}), _gare_du_mois),
]
BADGES_PAR_CODE = {badge.code: badge for badge in BADGES}
