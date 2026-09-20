from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    headquarters_city = models.CharField(max_length=255)
    created_at = models.DateField(verbose_name="date de création")

    class Meta:
        verbose_name = "compagnie"
        verbose_name_plural = "compagnies"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    SUPERADMIN = "superadmin", "Super administrateur"
    PDG = "pdg", "PDG"
    SECRETAIRE_GENERAL = "secretaire_general", "Secrétaire général"
    QHSE = "qhse", "QHSE"
    DIRECTEUR_EXPLOITATION = "directeur_exploitation", "Directeur exploitation"
    CHEF_GARE = "chef_gare", "Chef de gare"
    CHEF_LIGNE = "chef_ligne", "Chef de ligne"
    GUICHETIER = "guichetier", "Guichetier"
    BAGAGISTE = "bagagiste", "Bagagiste"
    CHAUFFEUR_PRINCIPAL = "chauffeur_principal", "Chauffeur principal"
    CHAUFFEUR_RELAIS = "chauffeur_relais", "Chauffeur relais"
    CONTROLEUR_LIGNE = "controleur_ligne", "Contrôleur de ligne"
    DIRECTEUR_TECHNIQUE = "directeur_technique", "Directeur technique"
    MAGASINIER = "magasinier", "Magasinier"
    CHEF_ATELIER = "chef_atelier", "Chef d'atelier"
    DRH = "drh", "DRH"
    DIRECTEUR_FINANCIER = "directeur_financier", "Directeur financier"
    RESPONSABLE_JURIDIQUE = "responsable_juridique", "Responsable juridique"


class User(AbstractUser):
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.SUPERADMIN)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(role=Role.SUPERADMIN, company__isnull=True)
                    | (~models.Q(role=Role.SUPERADMIN) & models.Q(company__isnull=False))
                ),
                name="user_company_required_unless_superadmin",
            )
        ]

    def clean(self):
        super().clean()
        if self.role == Role.SUPERADMIN and self.company_id is not None:
            raise ValidationError(
                "Un utilisateur superadmin ne doit pas être rattaché à une compagnie."
            )
        if self.role != Role.SUPERADMIN and self.company_id is None:
            raise ValidationError("Une compagnie est requise pour ce rôle.")

    def __str__(self):
        return self.username
