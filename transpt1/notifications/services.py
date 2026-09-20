import logging

from django.conf import settings

from notifications.models import CanalNotification, NotificationLog, StatutNotification
from notifications.providers import (
    FOURNISSEUR_ORANGE,
    FOURNISSEUR_TWILIO,
    choisir_fournisseur,
    envoyer_via_orange,
    envoyer_via_twilio,
    normaliser_numero,
)

logger = logging.getLogger(__name__)

ENVOI_PAR_FOURNISSEUR = {
    FOURNISSEUR_ORANGE: envoyer_via_orange,
    FOURNISSEUR_TWILIO: envoyer_via_twilio,
}


def envoyer_sms(destinataire, contenu, *, company, ticket=None):
    """Envoie un SMS (ou le simule) et trace systématiquement la tentative.

    Le fournisseur est choisi selon le numéro (voir ``choisir_fournisseur``). En
    mode simulation (par défaut, voir NOTIFICATIONS_SIMULATION_MODE), aucun appel
    n'est fait au fournisseur réel : le message est seulement journalisé, pour ne
    jamais déclencher de frais SMS pendant le développement ou les tests.
    """
    destinataire = normaliser_numero(destinataire)
    fournisseur = choisir_fournisseur(destinataire)

    def tracer(statut, **extra):
        return NotificationLog.objects.create(
            company=company,
            ticket=ticket,
            destinataire=destinataire,
            canal=CanalNotification.SMS,
            fournisseur=fournisseur,
            contenu=contenu,
            statut=statut,
            **extra,
        )

    if settings.NOTIFICATIONS_SIMULATION_MODE:
        logger.info("[SIMULATION SMS via %s] à %s : %s", fournisseur, destinataire, contenu)
        return tracer(StatutNotification.SIMULE)

    envoyer = ENVOI_PAR_FOURNISSEUR[fournisseur]
    try:
        reference = envoyer(destinataire, contenu)
    except Exception as exc:
        logger.exception("Échec de l'envoi du SMS à %s via %s", destinataire, fournisseur)
        return tracer(StatutNotification.ECHEC, erreur=str(exc))

    return tracer(StatutNotification.ENVOYE, reference_fournisseur=reference)
