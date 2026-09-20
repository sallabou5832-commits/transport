from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import Company
from reseau.models import Vehicule, VehiculeStatut


class Piece(models.Model):
    nom = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, unique=True)
    quantite_stock = models.PositiveIntegerField(default=0)
    seuil_alerte = models.PositiveIntegerField(default=0)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="pieces")

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.reference})"

    @property
    def en_alerte(self):
        return self.quantite_stock <= self.seuil_alerte


class StatutOrdreReparation(models.TextChoices):
    OUVERT = "ouvert", "Ouvert"
    EN_COURS = "en_cours", "En cours"
    TERMINE = "termine", "Terminé"


class OrdreReparation(models.Model):
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="ordres_reparation")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="ordres_reparation")
    description = models.TextField()
    statut = models.CharField(
        max_length=20, choices=StatutOrdreReparation.choices, default=StatutOrdreReparation.OUVERT
    )
    mecanicien = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="ordres_reparation"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    temps_passe_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"OR {self.id} - {self.vehicule} ({self.statut})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_statut = None
        if not is_new:
            old_statut = (
                OrdreReparation.objects.filter(pk=self.pk).values_list("statut", flat=True).first()
            )

        if self.statut == StatutOrdreReparation.TERMINE and self.date_cloture is None:
            self.date_cloture = timezone.now()

        super().save(*args, **kwargs)

        if is_new:
            if (
                self.vehicule.statut
                in (VehiculeStatut.BLOQUE_SECURITE, VehiculeStatut.EN_MAINTENANCE)
                and self.vehicule.statut != VehiculeStatut.EN_MAINTENANCE
            ):
                self.vehicule.statut = VehiculeStatut.EN_MAINTENANCE
                self.vehicule.save(update_fields=["statut"])
        elif old_statut != StatutOrdreReparation.TERMINE and self.statut == StatutOrdreReparation.TERMINE:
            self.vehicule.statut = VehiculeStatut.DISPONIBLE
            self.vehicule.save(update_fields=["statut"])


class SortiePiece(models.Model):
    ordre_reparation = models.ForeignKey(
        OrdreReparation, on_delete=models.PROTECT, related_name="sorties_pieces"
    )
    piece = models.ForeignKey(Piece, on_delete=models.PROTECT, related_name="sorties")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="sorties_pieces")
    quantite = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.quantite} x {self.piece} (OR {self.ordre_reparation_id})"
