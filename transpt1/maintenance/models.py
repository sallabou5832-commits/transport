import datetime

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import Company
from reseau.models import Vehicule, VehiculeStatut


class Piece(models.Model):
    nom = models.CharField(max_length=255)
    reference = models.CharField(max_length=100)
    quantite_stock = models.PositiveIntegerField(default=0)
    seuil_alerte = models.PositiveIntegerField(default=0)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="pieces")

    class Meta:
        ordering = ["nom"]
        constraints = [
            # Une référence constructeur est commune à toutes les compagnies : l'unicité est par compagnie, sans quoi
            # une compagnie apprendrait qu'une autre utilise cette référence (et ne pourrait pas la saisir).
            models.UniqueConstraint(fields=["company", "reference"], name="piece_reference_unique_par_compagnie")
        ]

    def __str__(self):
        return f"{self.nom} ({self.reference})"

    @property
    def en_alerte(self):
        return self.quantite_stock <= self.seuil_alerte


class StatutOrdreReparation(models.TextChoices):
    OUVERT = "ouvert", "Ouvert"
    EN_COURS = "en_cours", "En cours"
    TERMINE = "termine", "Terminé"


class UrgenceReparation(models.TextChoices):
    CRITIQUE = "critique", "Critique"
    HAUTE = "haute", "Haute"
    NORMALE = "normale", "Normale"
    BASSE = "basse", "Basse"


# Rang d'une urgence dans la file d'attente : le plus urgent d'abord.
RANG_URGENCE = {UrgenceReparation.CRITIQUE: 0, UrgenceReparation.HAUTE: 1, UrgenceReparation.NORMALE: 2, UrgenceReparation.BASSE: 3}


class PlanEntretien(models.Model):
    """Entretien préventif d'un véhicule (vidange, contrôle technique, révision…), à renouveler tous les N jours et/ou tous les
    N kilomètres. Quand l'échéance approche, l'atelier en est prévenu et, si le plan le prévoit, l'ordre de réparation est ouvert
    tout seul (cahier des charges : « planning de maintenance préventive automatisé avec alerte avant échéance »)."""

    vehicule = models.ForeignKey(Vehicule, on_delete=models.CASCADE, related_name="plans_entretien")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="plans_entretien")
    libelle = models.CharField(max_length=120)
    periodicite_jours = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    periodicite_km = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    # Dernière fois que l'entretien a été fait ; à la création, sans précision, c'est aujourd'hui et le kilométrage actuel.
    derniere_date = models.DateField(null=True, blank=True)
    dernier_km = models.PositiveIntegerField(null=True, blank=True)
    duree_estimee_heures = models.PositiveIntegerField(default=4, validators=[MinValueValidator(1)])
    declenche_ordre = models.BooleanField(default=True)
    actif = models.BooleanField(default=True)
    # Obligation réglementaire (contrôle technique, visite technique…) : elle entre dans le tableau de conformité du QHSE et du juridique.
    reglementaire = models.BooleanField(default=False)

    class Meta:
        ordering = ["vehicule__immatriculation", "libelle"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(periodicite_jours__isnull=False) | models.Q(periodicite_km__isnull=False),
                name="plan_entretien_a_une_periodicite",
            )
        ]

    def __str__(self):
        return f"{self.libelle} — {self.vehicule}"


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
    # File d'attente de l'atelier : classée par urgence, puis par la position que le directeur technique lui donne, puis par
    # ancienneté. Le délai estimé remonte au régulateur (retour prévu du véhicule).
    urgence = models.CharField(max_length=10, choices=UrgenceReparation.choices, default=UrgenceReparation.NORMALE)
    position = models.PositiveIntegerField(default=0)
    delai_estime_heures = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    # Entretien préventif à l'origine de l'ordre (il se renouvelle à la clôture).
    plan_entretien = models.ForeignKey(PlanEntretien, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordres")

    class Meta:
        ordering = ["-date_creation"]

    @property
    def retour_estime(self):
        """Quand le véhicule doit être de retour : l'ouverture de l'ordre plus le délai estimé (vide sans estimation)."""
        if self.statut == StatutOrdreReparation.TERMINE:
            return self.date_cloture
        if self.delai_estime_heures is None or self.date_creation is None:
            return None
        return self.date_creation + datetime.timedelta(hours=self.delai_estime_heures)

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
            self._alerter_vehicule_libere()
            if self.plan_entretien_id:  # l'entretien préventif est fait : le plan repart de zéro
                from maintenance.preventif import renouveler_apres_ordre

                renouveler_apres_ordre(self)

    def _alerter_vehicule_libere(self):
        """La clôture libère le véhicule pour le régulateur : il en est prévenu, ainsi que les gares concernées."""
        from alertes.models import GraviteAlerte, TypeAlerte
        from alertes.services import alerter, chefs_de_gare_du_vehicule
        from core.models import Role

        alerter(
            self.company,
            type=TypeAlerte.VEHICULE_LIBERE,
            gravite=GraviteAlerte.INFO,
            titre=f"Véhicule disponible : {self.vehicule.immatriculation}",
            message=f"Intervention terminée à l'atelier : {self.description}",
            roles=[Role.CHEF_LIGNE],
            destinataires=chefs_de_gare_du_vehicule(self.vehicule),
            objet=self,
        )


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


class StatutDemandePiece(models.TextChoices):
    DEMANDEE = "demandee", "Demandée"
    SERVIE = "servie", "Servie"
    REFUSEE = "refusee", "Indisponible"
    ANNULEE = "annulee", "Annulée"


class DemandePiece(models.Model):
    """Demande d'une pièce au magasinier, faite par l'atelier pour un ordre de réparation. Le magasinier voit tout de suite
    si le stock suffit ; la servir enregistre la sortie (le stock baisse) sur l'ordre."""

    ordre_reparation = models.ForeignKey(OrdreReparation, on_delete=models.CASCADE, related_name="demandes_pieces")
    piece = models.ForeignKey(Piece, on_delete=models.PROTECT, related_name="demandes")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="demandes_pieces")
    quantite = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    demandeur = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="+")
    statut = models.CharField(max_length=10, choices=StatutDemandePiece.choices, default=StatutDemandePiece.DEMANDEE)
    # Confirmation de disponibilité : le stock au moment de la demande couvrait-il la quantité ?
    disponible_a_la_demande = models.BooleanField(default=False)
    traitee_par = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    traitee_le = models.DateTimeField(null=True, blank=True)
    commentaire = models.CharField(max_length=255, blank=True)
    sortie = models.OneToOneField(SortiePiece, null=True, blank=True, on_delete=models.SET_NULL, related_name="demande")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]

    def __str__(self):
        return f"{self.quantite} x {self.piece} pour l'OR {self.ordre_reparation_id} ({self.get_statut_display().lower()})"
