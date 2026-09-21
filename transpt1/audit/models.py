from django.db import models
from django.utils import timezone

from core.models import Company, User


class JournalImmuable(Exception):
    """Le journal d'audit est en ajout seulement : aucune entrée ne se modifie ni ne se supprime."""


class ActionAudit(models.TextChoices):
    CREATION = "creation", "Création"
    MODIFICATION = "modification", "Modification"
    SUPPRESSION = "suppression", "Suppression"
    ANNULATION = "annulation", "Annulation"
    CONNEXION = "connexion", "Connexion"
    CONNEXION_ECHEC = "connexion_echec", "Échec de connexion"


class JournalQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise JournalImmuable("Le journal d'audit ne se modifie pas.")

    def delete(self):
        raise JournalImmuable("Le journal d'audit ne se supprime pas.")


class JournalAudit(models.Model):
    """Une action, tracée : qui, quoi, sur quel objet, quand, d'où, et ce qui a changé."""

    date = models.DateTimeField(default=timezone.now, db_index=True)
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.PROTECT, related_name="journal_audit"
    )
    # Le compte peut disparaître un jour : le nom et le rôle sont copiés pour que l'entrée reste lisible.
    acteur = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="actions_auditees"
    )
    acteur_nom = models.CharField(max_length=150, blank=True)
    acteur_role = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=20, choices=ActionAudit.choices)
    objet_type = models.CharField(max_length=100, blank=True)  # « billetterie.ticket »
    objet_id = models.CharField(max_length=64, blank=True)
    objet_repr = models.CharField(max_length=255, blank=True)
    # Création : l'état initial. Modification : {champ: [avant, après]}. Suppression : l'état supprimé.
    changements = models.JSONField(default=dict, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = JournalQuerySet.as_manager()

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        indexes = [
            models.Index(fields=["company", "-date"], name="audit_company_date"),
            models.Index(fields=["objet_type", "objet_id"], name="audit_objet"),
        ]

    def __str__(self):
        return f"{self.date:%Y-%m-%d %H:%M} {self.acteur_nom or 'système'} {self.action} {self.objet_type} {self.objet_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise JournalImmuable("Le journal d'audit ne se modifie pas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise JournalImmuable("Le journal d'audit ne se supprime pas.")
