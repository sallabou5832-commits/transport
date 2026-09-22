"""Un incident grave prévient la tutelle tout seul, sans que `personnel_roulant` ait besoin de connaître l'app
`tutelle` : ce module écoute la sauvegarde d'un `Incident`, connecté depuis `TutelleConfig.ready()`."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from personnel_roulant.models import Incident
from tutelle.generation import generer_flux_securite

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Incident)
def prevenir_la_tutelle_dun_incident_grave(sender, instance, **kwargs):
    """Un échec ne doit jamais empêcher de déclarer l'incident : il est journalisé, pas propagé (même principe que
    `alertes.services.alerter`)."""
    try:
        generer_flux_securite(instance)
    except Exception:  # noqa: BLE001
        logger.exception("Impossible de générer le flux tutelle pour l'incident %s", instance.pk)
