"""Émission des alertes inter-pôles.

Une action d'un pôle qui en concerne un autre (un défaut de sécurité, une panne, un stock bas…) appelle `alerter()`.
L'alerte ne doit jamais empêcher l'action qui la déclenche : un échec est journalisé, pas propagé.
"""

import logging

from django.db import transaction

from alertes.models import Alerte, GraviteAlerte, TypeAlerte

logger = logging.getLogger(__name__)


def alerter(
    company,
    *,
    type=TypeAlerte.AUTRE,  # noqa: A002 — même nom que le champ du modèle
    titre,
    message="",
    gravite=GraviteAlerte.INFO,
    roles=(),
    destinataires=(),
    objet=None,
    cle=None,
    cree_par=None,
):
    """Crée une alerte visible des `roles` (tous les agents de la compagnie ayant ce poste) et des `destinataires`
    (agents précis). Renvoie l'alerte, ou None si personne n'est visé, si `cle` a déjà servi, ou en cas d'échec.

    `cle` sert aux alertes générées automatiquement : la même situation ne prévient qu'une fois.
    """
    if company is None:
        return None
    roles = sorted({str(role) for role in roles})
    agents = {agent.pk: agent for agent in destinataires if agent is not None and agent.company_id == company.pk}
    if not roles and not agents:
        return None
    try:
        with transaction.atomic():
            if cle is not None and Alerte.objects.filter(company=company, cle=cle).exists():
                return None
            alerte = Alerte.objects.create(
                company=company,
                type=type,
                gravite=gravite,
                titre=titre[:200],
                message=message,
                roles_destinataires=roles,
                objet_type=objet._meta.label_lower if objet is not None else "",
                objet_id=str(objet.pk) if objet is not None else "",
                cree_par=cree_par if getattr(cree_par, "pk", None) else None,
                cle=cle,
            )
            if agents:
                alerte.destinataires.set(agents)
            return alerte
    except Exception:  # noqa: BLE001 — une alerte manquée ne doit jamais faire échouer l'action métier
        logger.exception("Impossible de créer l'alerte « %s »", titre)
        return None


def chef_de_gare_du_depart(depart):
    """Le chef de la gare de départ d'un départ (ou None)."""
    return depart.ligne.gare_depart.chef


def chefs_de_gare_du_vehicule(vehicule):
    """Les chefs des gares de départ des trajets à venir (planifiés ou en cours) de ce véhicule : ce sont eux que
    l'immobilisation du car concerne. Vide si le véhicule n'a aucun départ à venir."""
    from billetterie.models import Depart, DepartStatut

    departs = Depart.objects.filter(
        vehicule=vehicule, statut__in=[DepartStatut.PLANIFIE, DepartStatut.EN_COURS]
    ).select_related("ligne__gare_depart__chef")
    return {depart.ligne.gare_depart.chef for depart in departs if depart.ligne.gare_depart.chef_id}
