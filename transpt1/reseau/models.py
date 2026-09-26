from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

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
    # Position pour la carte du réseau (facultative : une gare sans coordonnées n'apparaît pas sur la carte).
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.company})"


class StatutLigne(models.TextChoices):
    OUVERTE = "ouverte", "Ouverte"
    FERMEE = "fermee", "Fermée"


class Ligne(models.Model):
    nom = models.CharField(max_length=255)
    gare_depart = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="lignes_depart")
    gare_arrivee = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="lignes_arrivee")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="lignes")
    # Prix du billet en FCFA. Renseigné, il est imposé à la vente (le guichetier ne saisit plus de prix) ; vide, la
    # ligne n'a pas de tarif et le prix reste saisi à la vente, comme avant.
    tarif = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))]
    )
    # Fermeture temporaire (PDG : « geler une ligne » ; directeur des opérations : fermer/rouvrir sur validation). Elle ne
    # se change que par `reseau.lignes`, jamais par une modification directe de la ligne.
    statut = models.CharField(max_length=10, choices=StatutLigne.choices, default=StatutLigne.OUVERTE)
    # Dernier jour de fermeture (inclus) : la ligne se rouvre d'elle-même le lendemain. Vide = jusqu'à réouverture décidée.
    fermee_jusqu_au = models.DateField(null=True, blank=True)
    motif_fermeture = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    @property
    def est_fermee(self):
        """Vrai tant que la fermeture court : une date de fin dépassée rouvre la ligne sans que personne n'ait à le faire."""
        if self.statut != StatutLigne.FERMEE:
            return False
        return self.fermee_jusqu_au is None or self.fermee_jusqu_au >= timezone.localdate()


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
    # Gare d'attache : d'où le véhicule part. Se change par l'arbitrage du directeur des opérations (`reaffecter-gare`), qui
    # prévient les deux gares ; vide tant que la compagnie n'a pas rattaché son parc.
    gare = models.ForeignKey(Gare, null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicules")
    # Compteur kilométrique : c'est lui qui déclenche l'entretien préventif (un plan se déclare en jours ou en kilomètres).
    # Relevé par le technique (directeur technique, chef d'atelier), pas par les chauffeurs.
    kilometrage = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["immatriculation"]

    def __str__(self):
        return self.immatriculation


class AffectationGare(models.Model):
    """Rattachement d'un agent de l'équipe locale (guichetier, bagagiste) à sa gare : c'est le chef de gare qui
    compose son équipe. Un agent n'est affecté qu'à une gare à la fois."""

    agent = models.OneToOneField("core.User", on_delete=models.CASCADE, related_name="affectation_gare")
    gare = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="affectations")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="affectations_gare")

    class Meta:
        ordering = ["gare__nom", "agent__username"]
        verbose_name = "affectation à une gare"
        verbose_name_plural = "affectations aux gares"

    def __str__(self):
        return f"{self.agent} → {self.gare.nom}"


class ActionChangementLigne(models.TextChoices):
    FERMER = "fermer", "Fermer"
    ROUVRIR = "rouvrir", "Rouvrir"


class StatutChangementLigne(models.TextChoices):
    EN_ATTENTE = "en_attente", "En attente de décision"
    VALIDE = "valide", "Validé"
    REFUSE = "refuse", "Refusé"


class ChangementLigne(models.Model):
    """Fermeture ou réouverture temporaire d'une ligne. Le chef de ligne et le chef de gare la demandent, le directeur des
    opérations la valide ; le directeur des opérations et le PDG l'appliquent directement (la demande est alors déjà validée)."""

    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE, related_name="changements")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="changements_ligne")
    action = models.CharField(max_length=10, choices=ActionChangementLigne.choices)
    motif = models.CharField(max_length=255)
    # Dernier jour de fermeture demandé (vide = jusqu'à réouverture). Sans objet pour une réouverture.
    jusqu_au = models.DateField(null=True, blank=True)
    demandeur = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="+")
    statut = models.CharField(
        max_length=12, choices=StatutChangementLigne.choices, default=StatutChangementLigne.EN_ATTENTE
    )
    decide_par = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decide_le = models.DateTimeField(null=True, blank=True)
    commentaire_decision = models.CharField(max_length=255, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]
        verbose_name = "changement d'état d'une ligne"
        verbose_name_plural = "changements d'état des lignes"

    def __str__(self):
        return f"{self.get_action_display()} {self.ligne.nom} ({self.get_statut_display().lower()})"
