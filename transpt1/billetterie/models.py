from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import Company
from reseau.models import Ligne, Vehicule


class DepartStatut(models.TextChoices):
    PLANIFIE = "planifie", "Planifié"
    EN_COURS = "en_cours", "En cours"
    TERMINE = "termine", "Terminé"


class Depart(models.Model):
    ligne = models.ForeignKey(Ligne, on_delete=models.PROTECT, related_name="departs")
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="departs")
    chauffeur = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="departs_conduits"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="departs")
    date_heure = models.DateTimeField()
    places_vendues = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=20, choices=DepartStatut.choices, default=DepartStatut.PLANIFIE
    )

    class Meta:
        ordering = ["-date_heure"]

    def __str__(self):
        return f"{self.ligne} - {self.date_heure:%Y-%m-%d %H:%M}"

    @property
    def places_restantes(self):
        return self.vehicule.capacite - self.places_vendues


class ModePaiement(models.TextChoices):
    ESPECES = "especes", "Espèces"
    MOBILE_MONEY = "mobile_money", "Mobile money"


class Ticket(models.Model):
    depart = models.ForeignKey(Depart, on_delete=models.PROTECT, related_name="tickets")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="tickets")
    passager_nom = models.CharField(max_length=255)
    passager_telephone = models.CharField(max_length=30)
    prix = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    mode_paiement = models.CharField(max_length=20, choices=ModePaiement.choices)
    vendu_par = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="tickets_vendus"
    )
    date_vente = models.DateTimeField(auto_now_add=True)
    # Clé fournie par le client (en-tête Idempotency-Key) : rejouer la même vente,
    # par exemple après une coupure réseau, ne crée pas un second ticket.
    cle_idempotence = models.CharField(max_length=64, null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-date_vente"]
        constraints = [
            models.UniqueConstraint(
                fields=["vendu_par", "cle_idempotence"],
                condition=models.Q(cle_idempotence__isnull=False),
                name="ticket_cle_idempotence_unique_par_vendeur",
            )
        ]

    def __str__(self):
        return f"Ticket {self.passager_nom} - {self.depart}"
