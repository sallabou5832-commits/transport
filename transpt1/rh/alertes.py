"""Alertes RH : formations obligatoires à renouveler (au DRH et au QHSE, et à l'agent), fins de contrat proches, risque de litige social
(au responsable juridique). Elles s'émettent à l'action qui les provoque et à chaque passage de `manage.py generer_alertes` ;
chaque situation ne prévient qu'une fois (clé d'alerte)."""

import datetime

from django.utils import timezone

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from core.models import Role, User
from rh.models import ContratAgent, Doleance, GraviteDoleance, TypeContrat
from rh.services import est_litige, suivi_formations

PREAVIS_FIN_CONTRAT_JOURS = 30


def formations_a_renouveler(company, maintenant):
    """Une alerte par formation obligatoire expirée ou entrant dans son préavis : le DRH et le QHSE (la sécurité routière est de son
    ressort), et l'agent concerné."""
    agents = {a.pk: a for a in User.objects.filter(company=company, is_active=True)}
    for ligne in suivi_formations(company, timezone.localdate(maintenant)):
        if ligne["etat"] not in ("expiree", "a_renouveler"):
            continue
        expiree, jours = ligne["etat"] == "expiree", ligne["jours_restants"]
        yield alerter(
            company,
            type=TypeAlerte.FORMATION,
            gravite=GraviteAlerte.CRITIQUE if expiree else GraviteAlerte.ATTENTION,
            titre=f"{ligne['obligation_nom']} {'expirée' if expiree else 'à renouveler'} : {ligne['agent_nom']}",
            message=(f"Échue depuis {-jours} jour(s)" if expiree else f"Échéance dans {jours} jour(s)")
            + f" ({ligne['date_expiration']:%d/%m/%Y}).",
            roles=[Role.DRH, Role.QHSE],
            destinataires=[agents[ligne["agent"]]],
            cle=f"formation:{ligne['agent']}:{ligne['obligation']}:{ligne['etat']}:{ligne['date_expiration']}",
        )


def contrats_a_terme(company, maintenant):
    """Un contrat à durée déterminée (ou de stage, ou journalier) qui se termine dans le mois : le DRH décide de le prolonger ou non."""
    aujourdhui = timezone.localdate(maintenant)
    limite = aujourdhui + datetime.timedelta(days=PREAVIS_FIN_CONTRAT_JOURS)
    contrats = ContratAgent.objects.filter(
        company=company, agent__is_active=True, date_fin__isnull=False, date_fin__gte=aujourdhui, date_fin__lte=limite
    ).exclude(type=TypeContrat.CDI).select_related("agent")
    for contrat in contrats:
        jours = (contrat.date_fin - aujourdhui).days
        yield alerter(
            company,
            type=TypeAlerte.CONTRAT,
            gravite=GraviteAlerte.ATTENTION,
            titre=f"Fin de contrat dans {jours} jour(s) : {contrat.agent.get_full_name() or contrat.agent.username}",
            message=f"{contrat.get_type_display()} qui se termine le {contrat.date_fin:%d/%m/%Y}.",
            roles=[Role.DRH],
            objet=contrat,
            cle=f"contrat:{contrat.pk}:{contrat.date_fin}",
        )


def signaler_litige(doleance):
    """Prévient le responsable juridique qu'une doléance a atteint le seuil de gravité : un litige social est à craindre. Le PDG l'est
    aussi quand la doléance est critique. L'alerte ne donne que l'objet et la gravité, pas l'identité du déposant."""
    critique = doleance.gravite == GraviteDoleance.CRITIQUE
    alerte = alerter(
        doleance.company,
        type=TypeAlerte.LITIGE,
        gravite=GraviteAlerte.CRITIQUE if critique else GraviteAlerte.ATTENTION,
        titre=f"Risque de litige social ({doleance.get_gravite_display().lower()}) : {doleance.objet}",
        message=f"Doléance déposée le {timezone.localtime(doleance.cree_le):%d/%m/%Y} au canal de médiation, gravité « {doleance.get_gravite_display().lower()} ».",
        roles=[Role.RESPONSABLE_JURIDIQUE, *([Role.PDG] if critique else [])],
        objet=doleance,
        cle=f"litige:{doleance.pk}:{doleance.gravite}",
    )
    if doleance.litige_signale_le is None:
        doleance.litige_signale_le = timezone.now()
        Doleance.objects.filter(pk=doleance.pk).update(litige_signale_le=doleance.litige_signale_le)
    return alerte


def litiges_a_signaler(company, maintenant):
    """Filet de sécurité : toute doléance ouverte au seuil de gravité que le juridique n'a pas encore reçue."""
    for doleance in Doleance.objects.filter(company=company, litige_signale_le__isnull=True):
        if est_litige(doleance):
            yield signaler_litige(doleance)
