from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from core.fichiers import CheminDeStockage


class Company(models.Model):
    name = models.CharField(max_length=255)
    headquarters_city = models.CharField(max_length=255)
    created_at = models.DateField(verbose_name="date de création")
    # Identité, coordonnées et mentions légales (écran « Ma compagnie », tenu par le PDG), à reprendre sur les billets, reçus,
    # manifestes et exports. Toutes facultatives : une compagnie qui n'a rien saisi fonctionne comme avant.
    sigle = models.CharField(max_length=20, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField("téléphone du service client", max_length=30, blank=True)
    email = models.EmailField(blank=True)
    rccm = models.CharField("RCCM", max_length=60, blank=True)
    compte_contribuable = models.CharField(max_length=30, blank=True)
    # Autorisation d'exercer l'activité de transport (décret n° 2015-269) : l'échéance est montrée, jamais imposée.
    autorisation_numero = models.CharField(max_length=60, blank=True)
    autorisation_echeance = models.DateField(null=True, blank=True)
    # Servi seulement par l'API (`/compagnie/logo/`), jamais par un lien public, comme toute pièce jointe.
    logo = models.FileField(upload_to=CheminDeStockage("logos"), null=True, blank=True)

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
    MECANICIEN = "mecanicien", "Mécanicien / électricien auto"
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
    # Suspension du compte par le PDG (« bloquer un compte guichetier ») : `is_active` passe à faux, ce qui coupe aussitôt
    # les sessions ouvertes ; ces champs disent quand, par qui et pourquoi.
    suspendu_le = models.DateTimeField(null=True, blank=True)
    suspendu_par = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    motif_suspension = models.CharField(max_length=255, blank=True)
    # Version des sessions du compte, portée par chaque jeton (`core.sessions`) : l'augmenter ferme d'un coup toutes les
    # sessions ouvertes (mot de passe changé, « déconnecter mes autres appareils »).
    version_session = models.PositiveIntegerField(default=0, editable=False)
    # Fiche du compte, tenue par le PDG ou le DRH (écran « Personnel et comptes ») ; toutes facultatives.
    telephone = models.CharField(max_length=30, blank=True)
    matricule = models.CharField(max_length=30, blank=True)
    # Mot de passe provisoire (compte créé ou mot de passe réinitialisé) : tant qu'il n'est pas changé, le compte ne fait rien
    # d'autre que le changer (voir `core.authentification`).
    doit_changer_mot_de_passe = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(role=Role.SUPERADMIN, company__isnull=True)
                    | (~models.Q(role=Role.SUPERADMIN) & models.Q(company__isnull=False))
                ),
                name="user_company_required_unless_superadmin",
            ),
            models.UniqueConstraint(
                fields=["company", "matricule"], condition=~models.Q(matricule=""), name="matricule_unique_par_compagnie"
            ),
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
