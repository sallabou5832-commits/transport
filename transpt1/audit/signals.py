"""Enregistrement automatique : chaque création, modification et suppression d'un objet métier laisse une entrée
dans le journal, avec l'acteur de la requête en cours (ou « système » hors requête : commande, migration)."""

import datetime
import decimal
import logging
import uuid

from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

from audit import contexte
from audit.models import ActionAudit, JournalAudit

logger = logging.getLogger(__name__)

# Modèle → champs ignorés. Un compteur dérivé (places vendues) ou un horodatage technique (dernière connexion)
# produirait du bruit : la vente qui le fait bouger est déjà tracée par son ticket.
REGISTRE = {
    "billetterie.Ticket": (),
    "billetterie.Depart": ("places_vendues",),
    "personnel_roulant.FeuilleDeRoute": (),
    "personnel_roulant.ChecklistDepart": (),
    "personnel_roulant.Incident": (),
    "maintenance.OrdreReparation": (),
    "maintenance.SortiePiece": (),
    "maintenance.Piece": (),
    "reseau.Vehicule": (),
    "reseau.Gare": (),
    "reseau.Ligne": (),
    "supports.DossierAgent": (),
    "supports.Assurance": (),
    "supports.Sinistre": (),
    "tutelle.FluxTutelle": (),
    "core.User": ("last_login",),
    "core.Company": (),
}
# Jamais écrits dans le journal, même chiffrés : seule l'existence du changement est tracée.
CHAMPS_SECRETS = {"password"}


def _valeur(valeur):
    if valeur is None or isinstance(valeur, (bool, int, float, str)):
        return valeur
    if isinstance(valeur, decimal.Decimal):
        return str(valeur)
    if isinstance(valeur, (datetime.datetime, datetime.date, datetime.time)):
        return valeur.isoformat()
    if isinstance(valeur, uuid.UUID):
        return str(valeur)
    return str(valeur)


def _champs(modele, ignores):
    return [f for f in modele._meta.concrete_fields if f.attname not in ignores and f.name not in ignores]


def _normalise(champ, valeur):
    """Valeur au type du champ (Decimal('5000') = Decimal('5000.00'), « 2030-01-01T10:00:00Z » = datetime) : sans
    cela, comparer une valeur pas encore relue de la base à celle relue produirait de faux changements."""
    try:
        return _valeur(champ.to_python(valeur))
    except Exception:  # noqa: BLE001 — une valeur inconvertible est comparée telle quelle
        return _valeur(valeur)


def _avant_enregistrement(sender, instance, **kwargs):
    instance._audit_avant = None
    if instance.pk is None or instance._state.adding:
        return
    champs = _champs(sender, REGISTRE[sender._meta.label])
    instance._audit_avant = (
        sender._default_manager.filter(pk=instance.pk).values(*[c.attname for c in champs]).first()
    )


def _apres_enregistrement(sender, instance, created, **kwargs):
    champs = _champs(sender, REGISTRE[sender._meta.label])
    apres = {c.attname: _normalise(c, getattr(instance, c.attname)) for c in champs}
    if created:
        action = ActionAudit.CREATION
        changements = {c: v for c, v in apres.items() if v not in (None, "")}
    else:
        avant = getattr(instance, "_audit_avant", None)
        if avant is None:
            return
        avant = {c.attname: _normalise(c, avant.get(c.attname)) for c in champs}
        changements = {c.attname: [avant[c.attname], apres[c.attname]] for c in champs if avant[c.attname] != apres[c.attname]}
        if not changements:
            return
        action = ActionAudit.MODIFICATION
        if sender._meta.label == "billetterie.Ticket" and changements.get("statut", [None, None])[1] == "annule":
            action = ActionAudit.ANNULATION
    _enregistrer(action, instance, changements)


def _apres_suppression(sender, instance, **kwargs):
    champs = _champs(sender, REGISTRE[sender._meta.label])
    _enregistrer(
        ActionAudit.SUPPRESSION, instance, {c.attname: _normalise(c, getattr(instance, c.attname)) for c in champs}
    )


def _enregistrer(action, instance, changements):
    for secret in CHAMPS_SECRETS & set(changements):
        changements[secret] = "modifié" if action == ActionAudit.MODIFICATION else "défini"
    try:
        meta = instance._meta
        acteur = contexte.acteur()
        try:
            representation = str(instance)[:255]
        except Exception:  # noqa: BLE001 — un __str__ qui échoue ne doit pas empêcher de tracer
            representation = f"{meta.label} #{instance.pk}"
        JournalAudit.objects.create(
            company_id=instance.pk if meta.label == "core.Company" else getattr(instance, "company_id", None),
            acteur=acteur,
            acteur_nom=(acteur.get_full_name() or acteur.username) if acteur else "système",
            acteur_role=acteur.role if acteur else "",
            action=action,
            objet_type=meta.label_lower,
            objet_id=str(instance.pk),
            objet_repr=representation,
            changements=changements,
            adresse_ip=contexte.adresse_ip(),
        )
    except Exception:  # noqa: BLE001
        # Ne jamais bloquer l'action métier, mais ne jamais perdre l'échec en silence non plus.
        logger.exception("Impossible d'écrire dans le journal d'audit (%s)", instance)


def brancher():
    for etiquette in REGISTRE:
        modele = apps.get_model(etiquette)
        pre_save.connect(_avant_enregistrement, sender=modele, dispatch_uid=f"audit-avant-{etiquette}")
        post_save.connect(_apres_enregistrement, sender=modele, dispatch_uid=f"audit-apres-{etiquette}")
        post_delete.connect(_apres_suppression, sender=modele, dispatch_uid=f"audit-suppr-{etiquette}")
