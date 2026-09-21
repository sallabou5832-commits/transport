from django.db import models
from django.utils import timezone

from billetterie.models import Depart
from core.models import Company
from reseau.models import Vehicule, VehiculeStatut

# Items de la checklist dont un défaut rend le véhicule dangereux à conduire.
# Le carburant, par exemple, n'en fait pas partie : un plein bas est un
# problème logistique, pas un problème de sécurité.
ITEMS_SECURITE = {"pneus", "freins", "direction", "eclairage", "ceintures", "extincteur"}


class FeuilleDeRoute(models.Model):
    depart = models.OneToOneField(Depart, on_delete=models.PROTECT, related_name="feuille_de_route")
    chauffeur = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="feuilles_de_route"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="feuilles_de_route")
    heure_depart_prevue = models.DateTimeField()
    heure_depart_reelle = models.DateTimeField(null=True, blank=True)
    heure_arrivee_prevue = models.DateTimeField(null=True, blank=True)
    heure_arrivee_reelle = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-heure_depart_prevue"]
        indexes = [models.Index(fields=["company", "heure_depart_prevue"], name="feuille_company_depart_prevu")]

    def __str__(self):
        return f"Feuille de route {self.depart} ({self.chauffeur})"

    @property
    def peut_demarrer(self):
        if self.heure_depart_reelle is not None:
            return False
        if self.depart.vehicule.statut == VehiculeStatut.BLOQUE_SECURITE:
            return False
        if self.checklist_items.filter(etat=EtatChecklist.DEFAUT, item__in=ITEMS_SECURITE).exists():
            return False
        return True


class EtatChecklist(models.TextChoices):
    OK = "ok", "OK"
    DEFAUT = "defaut", "Défaut"


class ChecklistDepart(models.Model):
    feuille_de_route = models.ForeignKey(
        FeuilleDeRoute, on_delete=models.CASCADE, related_name="checklist_items"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="checklist_items")
    item = models.CharField(max_length=100)
    etat = models.CharField(max_length=10, choices=EtatChecklist.choices)
    commentaire = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "item de checklist"
        verbose_name_plural = "items de checklist"

    def __str__(self):
        return f"{self.item} - {self.etat}"

    @property
    def est_item_securite(self):
        return self.item.strip().lower() in ITEMS_SECURITE

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.etat == EtatChecklist.DEFAUT and self.est_item_securite:
            vehicule = self.feuille_de_route.depart.vehicule
            if vehicule.statut != VehiculeStatut.BLOQUE_SECURITE:
                vehicule.statut = VehiculeStatut.BLOQUE_SECURITE
                vehicule.save(update_fields=["statut"])


class TypeIncident(models.TextChoices):
    PANNE = "panne", "Panne"
    ACCIDENT = "accident", "Accident"
    RETARD = "retard", "Retard"
    AUTRE = "autre", "Autre"


class GraviteIncident(models.TextChoices):
    FAIBLE = "faible", "Faible"
    MOYENNE = "moyenne", "Moyenne"
    GRAVE = "grave", "Grave"


class StatutIncident(models.TextChoices):
    OUVERT = "ouvert", "Ouvert"
    TRAITE = "traite", "Traité"


class Incident(models.Model):
    feuille_de_route = models.ForeignKey(
        FeuilleDeRoute,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
    )
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="incidents")
    chauffeur = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="incidents_signales"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="incidents")
    type_incident = models.CharField(max_length=20, choices=TypeIncident.choices)
    description = models.TextField()
    date = models.DateTimeField(default=timezone.now)
    gravite = models.CharField(max_length=10, choices=GraviteIncident.choices)
    statut = models.CharField(
        max_length=10, choices=StatutIncident.choices, default=StatutIncident.OUVERT
    )

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["company", "statut", "date"], name="incident_company_statut_date")]

    def __str__(self):
        return f"Incident {self.type_incident} - {self.vehicule} ({self.gravite})"
