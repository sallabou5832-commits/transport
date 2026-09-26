from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.fichiers import CheminDeStockage
from core.models import Company, User
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
    reference_assureur = models.CharField(max_length=100, blank=True)
    montant_estime = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    montant_indemnise = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    clos_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Sinistre {self.id} ({self.statut})"


class PieceSinistre(models.Model):
    """Une pièce du dossier d'un sinistre (constat, photos, expertise, courrier de l'assureur), servie par l'API seulement."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="pieces_sinistre")
    sinistre = models.ForeignKey(Sinistre, on_delete=models.CASCADE, related_name="pieces")
    fichier = models.FileField(upload_to=CheminDeStockage("sinistres"))
    nom_fichier = models.CharField(max_length=200)
    libelle = models.CharField(max_length=200, blank=True)
    taille = models.PositiveIntegerField()
    ajoute_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cree_le", "id"]

    def __str__(self):
        return f"{self.nom_fichier} ({self.sinistre})"


class CategorieModele(models.TextChoices):
    TRAVAIL = "travail", "Contrats et documents de travail"
    SINISTRE = "sinistre", "Assurance et sinistres"
    COMMERCIAL = "commercial", "Conditions de transport et clients"
    COURRIER = "courrier", "Courriers types"
    REGLEMENT = "reglement", "Règlements et chartes"
    AUTRE = "autre", "Autre"


class ModeleJuridique(models.Model):
    """Un document juridique type (contrat, attestation, constat, courrier…) que les autres pôles peuvent consulter et reprendre : le
    texte du modèle, et/ou un fichier. `poles` limite la consultation à certains pôles (vide : tous)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="modeles_juridiques")
    titre = models.CharField(max_length=200)
    categorie = models.CharField(max_length=12, choices=CategorieModele.choices, default=CategorieModele.AUTRE)
    description = models.TextField(blank=True)
    contenu = models.TextField(blank=True)
    poles = models.JSONField(default=list, blank=True)
    version = models.CharField(max_length=20, default="1.0")
    fichier = models.FileField(upload_to=CheminDeStockage("modeles"), null=True, blank=True)
    nom_fichier = models.CharField(max_length=200, blank=True)
    taille = models.PositiveIntegerField(null=True, blank=True)
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categorie", "titre"]
        constraints = [models.UniqueConstraint(fields=["company", "titre"], name="modele_juridique_unique")]

    def __str__(self):
        return self.titre
