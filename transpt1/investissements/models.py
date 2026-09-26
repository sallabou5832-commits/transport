from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import Company, User


class TypeInvestissement(models.TextChoices):
    ACHAT_VEHICULE = "achat_vehicule", "Achat de véhicules"
    OUVERTURE_LIGNE = "ouverture_ligne", "Ouverture de ligne"
    AUTRE = "autre", "Autre investissement"


class StatutInvestissement(models.TextChoices):
    EN_ATTENTE = "en_attente", "En attente de décision"
    VALIDE = "valide", "Validé"
    REFUSE = "refuse", "Refusé"


class Investissement(models.Model):
    """Demande d'investissement (achat de cars, ouverture de ligne…) que seul le PDG valide : c'est l'un des rares points où la
    direction générale décide à la place du terrain (cahier des charges : « validation des investissements »)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="investissements")
    type = models.CharField(max_length=20, choices=TypeInvestissement.choices, default=TypeInvestissement.AUTRE)
    libelle = models.CharField(max_length=200)
    justification = models.TextField(blank=True)
    montant = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    # Nombre de véhicules demandés (achat), pour éclairer le montant.
    quantite = models.PositiveIntegerField(null=True, blank=True)
    demandeur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    statut = models.CharField(max_length=12, choices=StatutInvestissement.choices, default=StatutInvestissement.EN_ATTENTE)
    decide_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decide_le = models.DateTimeField(null=True, blank=True)
    commentaire_decision = models.CharField(max_length=255, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]

    def __str__(self):
        return f"{self.libelle} ({self.get_statut_display().lower()})"
