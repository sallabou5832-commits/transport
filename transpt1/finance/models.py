from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import Company, User
from reseau.models import Gare, Ligne, Vehicule

MONTANT_MIN = Decimal("0.01")


class CategorieDepense(models.TextChoices):
    CARBURANT = "carburant", "Carburant"
    MAINTENANCE = "maintenance", "Maintenance"
    SALAIRES = "salaires", "Salaires"
    ASSURANCE = "assurance", "Assurance"
    FOURNISSEUR = "fournisseur", "Achats et fournisseurs"
    AUTRE = "autre", "Autre"


class Depense(models.Model):
    """Une dépense de la compagnie, rattachée si possible à une ligne, à un véhicule ou à une gare : c'est ce qui permet de la
    comparer aux recettes (rentabilité) et au budget (carburant). Une facture payée en crée une automatiquement."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="depenses")
    date = models.DateField()
    categorie = models.CharField(max_length=12, choices=CategorieDepense.choices, default=CategorieDepense.AUTRE)
    libelle = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONTANT_MIN)])
    ligne = models.ForeignKey(Ligne, null=True, blank=True, on_delete=models.SET_NULL, related_name="depenses")
    vehicule = models.ForeignKey(Vehicule, null=True, blank=True, on_delete=models.SET_NULL, related_name="depenses")
    gare = models.ForeignKey(Gare, null=True, blank=True, on_delete=models.SET_NULL, related_name="depenses")
    saisi_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["company", "date"], name="depense_company_date")]

    def __str__(self):
        return f"{self.libelle} ({self.montant})"


class BudgetCarburant(models.Model):
    """Budget carburant d'une ligne pour un mois : la finance est alertée à 80 % puis au dépassement."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="budgets_carburant")
    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE, related_name="budgets_carburant")
    mois = models.DateField(help_text="Premier jour du mois.")
    montant = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONTANT_MIN)])

    class Meta:
        ordering = ["-mois", "ligne__nom"]
        constraints = [models.UniqueConstraint(fields=["company", "ligne", "mois"], name="budget_carburant_unique")]

    def __str__(self):
        return f"{self.ligne} {self.mois:%m/%Y}"


class Fournisseur(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="fournisseurs")
    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["nom"]
        constraints = [models.UniqueConstraint(fields=["company", "nom"], name="fournisseur_unique_par_compagnie")]

    def __str__(self):
        return self.nom


class TypeFacture(models.TextChoices):
    FOURNISSEUR = "fournisseur", "Fournisseur"
    ASSURANCE = "assurance", "Assurance"
    AUTRE = "autre", "Autre"


class StatutFacture(models.TextChoices):
    A_PAYER = "a_payer", "À payer"
    PAYEE = "payee", "Payée"
    ANNULEE = "annulee", "Annulée"


class Facture(models.Model):
    """Une somme à payer à un fournisseur ou à un assureur, avec son échéance : elle alimente l'échéancier, les rappels et la
    trésorerie prévisionnelle. La payer enregistre la dépense correspondante."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="factures")
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.PROTECT, related_name="factures")
    type = models.CharField(max_length=12, choices=TypeFacture.choices, default=TypeFacture.FOURNISSEUR)
    reference = models.CharField(max_length=100, blank=True)
    libelle = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONTANT_MIN)])
    date_emission = models.DateField()
    echeance = models.DateField()
    statut = models.CharField(max_length=10, choices=StatutFacture.choices, default=StatutFacture.A_PAYER)
    payee_le = models.DateField(null=True, blank=True)
    mode_paiement = models.CharField(max_length=20, blank=True)
    depense = models.OneToOneField(Depense, null=True, blank=True, on_delete=models.SET_NULL, related_name="facture")
    saisi_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["echeance", "id"]

    def __str__(self):
        return f"{self.fournisseur} — {self.libelle}"


class ConfigurationFinance(models.Model):
    """Réglages financiers d'une compagnie : le solde de caisse de départ, à partir duquel la trésorerie est calculée."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="configuration_finance")
    solde_initial = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    def __str__(self):
        return f"Finance de {self.company}"
