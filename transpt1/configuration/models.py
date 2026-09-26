from django.db import models
from django.utils import timezone

from configuration.regles import AisanceNumerique, NiveauAutomatisation, NiveauGamification
from core.models import Company, Role, User


class ConfigurationCompagnie(models.Model):
    """Le cadre de la compagnie, fixé par le PDG : aucun poste ne peut dépasser ces plafonds."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="configuration")
    automatisation_max = models.CharField(
        max_length=12, choices=NiveauAutomatisation.CHOIX, default=NiveauAutomatisation.AUTOMATIQUE
    )
    gamification_max = models.CharField(
        max_length=10, choices=NiveauGamification.CHOIX, default=NiveauGamification.COMPLET
    )
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "cadre de la compagnie"
        verbose_name_plural = "cadres des compagnies"

    def __str__(self):
        return f"Cadre de {self.company}"


class ConfigurationPoste(models.Model):
    """Les réglages d'un poste dans une compagnie, faits par l'échelon directement supérieur (ou le PDG). Une valeur
    vide (`null`) laisse le défaut du socle."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="configurations_postes")
    role = models.CharField(max_length=32, choices=[(r.value, r.label) for r in Role if r != Role.SUPERADMIN])
    niveau_automatisation = models.CharField(
        max_length=12, choices=NiveauAutomatisation.CHOIX, null=True, blank=True
    )
    niveau_gamification = models.CharField(max_length=10, choices=NiveauGamification.CHOIX, null=True, blank=True)
    # Codes de `regles.FONCTIONS` retirés à ce poste.
    fonctions_desactivees = models.JSONField(default=list, blank=True)
    prefere_vocal = models.BooleanField(default=False)
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "configuration d'un poste"
        verbose_name_plural = "configurations des postes"
        constraints = [models.UniqueConstraint(fields=["company", "role"], name="configuration_poste_unique")]

    def __str__(self):
        return f"{self.role} ({self.company})"


class ConfigurationAgent(models.Model):
    """Ajustement pour un agent précis, qui tient compte de sa propre aisance avec le numérique et de sa préférence pour
    le mode vocal : le niveau d'un poste n'est pas forcément celui de chacun de ceux qui l'occupent."""

    agent = models.OneToOneField(User, on_delete=models.CASCADE, related_name="configuration_agent")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="configurations_agents")
    niveau_automatisation = models.CharField(
        max_length=12, choices=NiveauAutomatisation.CHOIX, null=True, blank=True
    )
    niveau_gamification = models.CharField(max_length=10, choices=NiveauGamification.CHOIX, null=True, blank=True)
    fonctions_desactivees = models.JSONField(default=list, blank=True)
    prefere_vocal = models.BooleanField(null=True, blank=True)
    aisance_numerique = models.CharField(
        max_length=10, choices=AisanceNumerique.CHOIX, default=AisanceNumerique.MOYENNE
    )
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "configuration d'un agent"
        verbose_name_plural = "configurations des agents"

    def __str__(self):
        return f"Configuration de {self.agent}"
