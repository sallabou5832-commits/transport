from django.db import models

from billetterie.models import Ticket
from core.models import Company


class CanalNotification(models.TextChoices):
    SMS = "sms", "SMS"
    WHATSAPP = "whatsapp", "WhatsApp"


class StatutNotification(models.TextChoices):
    ENVOYE = "envoye", "Envoyé"
    ECHEC = "echec", "Échec"
    SIMULE = "simule", "Simulé"


class NotificationLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="notifications")
    ticket = models.ForeignKey(
        Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    destinataire = models.CharField(max_length=30)
    canal = models.CharField(max_length=20, choices=CanalNotification.choices, default=CanalNotification.SMS)
    contenu = models.TextField()
    statut = models.CharField(max_length=20, choices=StatutNotification.choices)
    reference_fournisseur = models.CharField(max_length=100, blank=True)
    erreur = models.TextField(blank=True)
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_envoi"]

    def __str__(self):
        return f"{self.canal} à {self.destinataire} ({self.statut})"
