"""Diffuser une note de service, envoyer un message de gare, annoncer un rendez-vous : chacun prévient les postes concernés par la cloche
d'alertes. Rien ici ne bloque l'action qui l'appelle (voir `alertes.services.alerter`)."""

from rest_framework.exceptions import ValidationError

from alertes.models import GraviteAlerte, TypeAlerte
from alertes.services import alerter
from communication.models import PorteeMessage
from core.serializers import nom_complet
from personnel_roulant.models import FeuilleDeRoute
from reseau.models import AffectationGare


def diffuser_note(note):
    alerter(
        note.company,
        type=TypeAlerte.NOTE_SERVICE,
        gravite=GraviteAlerte.ATTENTION if note.urgente else GraviteAlerte.INFO,
        titre=f"Note de service : {note.titre}",
        message=note.contenu[:500],
        roles=note.roles_destinataires,
        objet=note,
        cree_par=note.auteur,
    )


def annoncer_evenement(evenement):
    if not evenement.participants:
        return
    quand = evenement.debut.strftime("%d/%m/%Y à %H:%M")
    lieu = f" — {evenement.lieu}" if evenement.lieu else ""
    alerter(
        evenement.company,
        type=TypeAlerte.AGENDA,
        gravite=GraviteAlerte.INFO,
        titre=f"Agenda : {evenement.titre}",
        message=f"{quand}{lieu}. Convoqué par {nom_complet(evenement.auteur)}.",
        roles=evenement.participants,
        objet=evenement,
        cree_par=evenement.auteur,
    )


def destinataires_du_message(gare, portee):
    """L'équipe locale de la gare (guichetiers, bagagistes) et/ou les conducteurs dont le car est en route vers elle."""
    agents = {}
    if portee in (PorteeMessage.EQUIPE, PorteeMessage.LES_DEUX):
        for affectation in AffectationGare.objects.filter(gare=gare).select_related("agent"):
            agents[affectation.agent_id] = affectation.agent
    if portee in (PorteeMessage.APPROCHE, PorteeMessage.LES_DEUX):
        en_route = FeuilleDeRoute.objects.filter(
            depart__ligne__gare_arrivee=gare, heure_depart_reelle__isnull=False, heure_arrivee_reelle__isnull=True
        ).select_related("chauffeur")
        for feuille in en_route:
            agents[feuille.chauffeur_id] = feuille.chauffeur
    return list(agents.values())


def envoyer_message(message):
    """Enregistre les destinataires du message et les prévient. Sans destinataire, le message n'a pas lieu d'être."""
    destinataires = destinataires_du_message(message.gare, message.portee)
    if not destinataires:
        raise ValidationError("Personne à prévenir : l'équipe de la gare est vide et aucun car n'est en route vers elle.")
    message.destinataires.set(destinataires)
    alerter(
        message.company,
        type=TypeAlerte.MESSAGE,
        gravite=GraviteAlerte.ATTENTION,
        titre=f"Message du chef de la gare {message.gare.nom}",
        message=message.texte,
        destinataires=destinataires,
        objet=message,
        cree_par=message.auteur,
    )
    return destinataires
