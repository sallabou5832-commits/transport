import logging

from django.conf import settings

from notifications.models import CanalNotification, NotificationLog, StatutNotification
from notifications.providers import (
    FOURNISSEUR_ORANGE,
    FOURNISSEUR_TWILIO,
    choisir_fournisseur,
    envoyer_via_orange,
    envoyer_via_twilio,
    envoyer_whatsapp_via_twilio,
    normaliser_numero,
)

logger = logging.getLogger(__name__)

ENVOI_SMS_PAR_FOURNISSEUR = {
    FOURNISSEUR_ORANGE: envoyer_via_orange,
    FOURNISSEUR_TWILIO: envoyer_via_twilio,
}


def _envoyer(canal, destinataire, contenu, *, company, ticket, variables):
    destinataire = normaliser_numero(destinataire)
    if canal == CanalNotification.WHATSAPP:
        fournisseur = FOURNISSEUR_TWILIO

        def envoyer():
            return envoyer_whatsapp_via_twilio(destinataire, contenu, variables)
    else:
        fournisseur = choisir_fournisseur(destinataire)

        def envoyer():
            return ENVOI_SMS_PAR_FOURNISSEUR[fournisseur](destinataire, contenu)

    def tracer(statut, **extra):
        return NotificationLog.objects.create(
            company=company,
            ticket=ticket,
            destinataire=destinataire,
            canal=canal,
            fournisseur=fournisseur,
            contenu=contenu,
            statut=statut,
            **extra,
        )

    if settings.NOTIFICATIONS_SIMULATION_MODE:
        logger.info("[SIMULATION %s via %s] à %s : %s", canal, fournisseur, destinataire, contenu)
        return tracer(StatutNotification.SIMULE)

    try:
        reference = envoyer()
    except Exception as exc:
        logger.exception("Échec de l'envoi %s à %s via %s", canal, destinataire, fournisseur)
        return tracer(StatutNotification.ECHEC, erreur=str(exc))

    return tracer(StatutNotification.ENVOYE, reference_fournisseur=reference)


def envoyer_sms(destinataire, contenu, *, company, ticket=None):
    """Envoie un SMS (ou le simule) et trace systématiquement la tentative.

    Le fournisseur est choisi selon le numéro (voir ``choisir_fournisseur``). En
    mode simulation (par défaut, voir NOTIFICATIONS_SIMULATION_MODE), aucun appel
    n'est fait au fournisseur réel : le message est seulement journalisé, pour ne
    jamais déclencher de frais pendant le développement ou les tests.
    """
    return _envoyer(
        CanalNotification.SMS, destinataire, contenu, company=company, ticket=ticket, variables=None
    )


def envoyer_whatsapp(destinataire, contenu, *, company, ticket=None, variables=None):
    """Envoie un message WhatsApp (ou le simule) et trace la tentative.

    ``variables`` alimente le modèle WhatsApp approuvé quand il est configuré
    (voir ``envoyer_whatsapp_via_twilio``). Même règle de simulation que le SMS.
    """
    return _envoyer(
        CanalNotification.WHATSAPP,
        destinataire,
        contenu,
        company=company,
        ticket=ticket,
        variables=variables,
    )


def notifier_vente_ticket(ticket, depart):
    """Prévient le passager de la confirmation de son billet, sur chaque canal activé.

    Les canaux (``NOTIFICATIONS_CANAUX_TICKET``) sont indépendants : l'échec de l'un
    n'empêche pas l'envoi des autres, et aucun n'interrompt la vente.
    """
    date = f"{depart.date_heure:%d/%m/%Y à %H:%M}"
    contenu = (
        f"Bonjour {ticket.passager_nom}, votre billet pour {depart.ligne.nom} le {date} "
        f"est confirmé. Prix : {ticket.prix} FCFA. Bon voyage !"
    )
    variables = {"1": ticket.passager_nom, "2": depart.ligne.nom, "3": date, "4": str(ticket.prix)}

    for canal in settings.NOTIFICATIONS_CANAUX_TICKET:
        if canal == CanalNotification.SMS:
            envoyer_sms(
                ticket.passager_telephone, contenu, company=ticket.company, ticket=ticket
            )
        elif canal == CanalNotification.WHATSAPP:
            envoyer_whatsapp(
                ticket.passager_telephone,
                contenu,
                company=ticket.company,
                ticket=ticket,
                variables=variables,
            )
        else:
            logger.warning("Canal de notification inconnu ignoré : %r", canal)
