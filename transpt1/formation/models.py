"""Formation par poste : parcours pédagogiques simulés.

Isolation stricte : ce module ne référence AUCUN modèle métier (billetterie,
personnel_roulant, maintenance, reseau, supports, notifications) et n'en importe
aucun. Une étape de formation est une action *simulée* : ses données fictives
vivent dans ``EtapeFormation.donnees_simulees`` et la progression de l'apprenant
n'écrit que dans les tables ``formation_*``. Rien de ce qui est fait en formation
ne peut donc apparaître dans les vrais modules.
"""

from django.core.validators import MinValueValidator
from django.db import models

from core.models import Role


class TypeAction(models.TextChoices):
    SIMULEE = "simulee", "Action simulée (n'affecte jamais les données réelles)"


class ParcoursFormation(models.Model):
    role = models.CharField(max_length=32, choices=Role.choices, unique=True)
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["role"]
        verbose_name = "parcours de formation"
        verbose_name_plural = "parcours de formation"

    def __str__(self):
        return f"{self.titre} ({self.get_role_display()})"


class EtapeFormation(models.Model):
    parcours = models.ForeignKey(ParcoursFormation, on_delete=models.CASCADE, related_name="etapes")
    ordre = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    titre = models.CharField(max_length=255)
    instructions = models.TextField()
    type_action = models.CharField(
        max_length=20, choices=TypeAction.choices, default=TypeAction.SIMULEE
    )
    # Identifiant du scénario simulé que l'interface doit afficher (ex. "vente_ticket").
    scenario = models.CharField(max_length=50, blank=True)
    # Données fictives servant de support à l'exercice (départ, passager, pièce...).
    # Elles sont propres à la formation et en lecture seule pour l'apprenant.
    donnees_simulees = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["parcours", "ordre"]
        verbose_name = "étape de formation"
        verbose_name_plural = "étapes de formation"
        constraints = [
            models.UniqueConstraint(fields=["parcours", "ordre"], name="etape_ordre_unique_par_parcours"),
        ]

    def __str__(self):
        return f"{self.parcours.role} #{self.ordre} - {self.titre}"


class ProgressionFormation(models.Model):
    user = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="progressions_formation"
    )
    parcours = models.ForeignKey(
        ParcoursFormation, on_delete=models.PROTECT, related_name="progressions"
    )
    # Étape à réaliser maintenant ; vide une fois le parcours terminé.
    etape_courante = models.ForeignKey(
        EtapeFormation, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    termine = models.BooleanField(default=False)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_debut"]
        verbose_name = "progression de formation"
        verbose_name_plural = "progressions de formation"
        constraints = [
            models.UniqueConstraint(fields=["user", "parcours"], name="progression_unique_par_user_parcours"),
            models.CheckConstraint(
                condition=(
                    models.Q(termine=False, date_fin__isnull=True)
                    | models.Q(termine=True, date_fin__isnull=False, etape_courante__isnull=True)
                ),
                name="progression_termine_coherent",
            ),
        ]

    def __str__(self):
        etat = "terminé" if self.termine else "en cours"
        return f"{self.user} - {self.parcours} ({etat})"
