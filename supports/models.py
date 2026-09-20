from django.db import models
from django.utils import timezone

from core.models import Company
from personnel_roulant.models import Incident
from reseau.models import Vehicule


class StatutDossierAgent(models.TextChoices):
    ACTIF = "actif", "Actif"
    SUSPENDU = "suspendu", "Suspendu"
    TERMINE = "termine", "Terminé"


class DossierAgent(models.Model):
    agent = models.OneToOneField(
        "core.User", on_delete=models.PROTECT, related_name="dossier_agent"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="dossiers_agents")
    date_embauche = models.DateField()
    poste = models.CharField(max_length=255)
    statut = models.CharField(
        max_length=20, choices=StatutDossierAgent.choices, default=StatutDossierAgent.ACTIF
    )
    notes_rh = models.TextField(blank=True)

    class Meta:
        ordering = ["agent__username"]

    def __str__(self):
        return f"Dossier {self.agent} ({self.poste})"


class Assurance(models.Model):
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="assurances")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="assurances")
    compagnie_assurance = models.CharField(max_length=255)
    numero_police = models.CharField(max_length=100)
    date_echeance = models.DateField()

    class Meta:
        ordering = ["date_echeance"]

    def __str__(self):
        return f"{self.numero_police} - {self.vehicule}"


class StatutSinistre(models.TextChoices):
    OUVERT = "ouvert", "Ouvert"
    EN_COURS = "en_cours", "En cours"
    CLOS = "clos", "Clos"


class Sinistre(models.Model):
    vehicule = models.ForeignKey(
        Vehicule, on_delete=models.PROTECT, null=True, blank=True, related_name="sinistres"
    )
    incident = models.ForeignKey(
        Incident, on_delete=models.PROTECT, null=True, blank=True, related_name="sinistres"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="sinistres")
    description = models.TextField()
    statut = models.CharField(
        max_length=20, choices=StatutSinistre.choices, default=StatutSinistre.OUVERT
    )
    date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Sinistre {self.id} ({self.statut})"
