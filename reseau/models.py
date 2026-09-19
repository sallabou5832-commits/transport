from django.db import models

from core.models import Company


class Gare(models.Model):
    nom = models.CharField(max_length=255)
    ville = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="gares")
    chef = models.OneToOneField(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gare_dirigee",
    )

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.company})"


class Ligne(models.Model):
    nom = models.CharField(max_length=255)
    gare_depart = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="lignes_depart")
    gare_arrivee = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="lignes_arrivee")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="lignes")

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class VehiculeStatut(models.TextChoices):
    DISPONIBLE = "disponible", "Disponible"
    EN_LIGNE = "en_ligne", "En ligne"
    EN_MAINTENANCE = "en_maintenance", "En maintenance"
    BLOQUE_SECURITE = "bloque_securite", "Bloqué sécurité"


class Vehicule(models.Model):
    immatriculation = models.CharField(max_length=20, unique=True)
    capacite = models.PositiveIntegerField()
    statut = models.CharField(
        max_length=20, choices=VehiculeStatut.choices, default=VehiculeStatut.DISPONIBLE
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="vehicules")

    class Meta:
        ordering = ["immatriculation"]

    def __str__(self):
        return self.immatriculation
