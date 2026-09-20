import logging

from django.conf import settings

from notifications.models import CanalNotification, NotificationLog, StatutNotification

logger = logging.getLogger(__name__)


def envoyer_sms(destinataire, contenu, *, company, ticket=None):
    """Envoie un SMS (ou le simule) et trace systématiquement la tentative.

    En mode simulation (par défaut, voir NOTIFICATIONS_SIMULATION_MODE), aucun
    appel n'est fait au fournisseur réel : le message est seulement journalisé,
    pour ne jamais déclencher de frais SMS pendant le développement ou les tests.
    """
    if settings.NOTIFICATIONS_SIMULATION_MODE:
        logger.info("[SIMULATION SMS] à %s : %s", destinataire, contenu)
        return NotificationLog.objects.create(
            company=company,
            ticket=ticket,
            destinataire=destinataire,
            canal=CanalNotification.SMS,
            contenu=contenu,
            statut=StatutNotification.SIMULE,
        )

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=contenu, from_=settings.TWILIO_FROM_NUMBER, to=destinataire
        )
    except Exception as exc:
        logger.exception("Échec de l'envoi du SMS à %s", destinataire)
        return NotificationLog.objects.create(
            company=company,
            ticket=ticket,
            destinataire=destinataire,
            canal=CanalNotification.SMS,
            contenu=contenu,
            statut=StatutNotification.ECHEC,
            erreur=str(exc),
        )

    return NotificationLog.objects.create(
        company=company,
        ticket=ticket,
        destinataire=destinataire,
        canal=CanalNotification.SMS,
        contenu=contenu,
        statut=StatutNotification.ENVOYE,
        reference_fournisseur=message.sid,
    )
