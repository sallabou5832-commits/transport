from django.db import models
from django.utils import timezone

from core.models import Company, User


class TypeAlerte(models.TextChoices):
    BLOCAGE_SECURITE = "blocage_securite", "Départ bloqué (sécurité)"
    DEFAUT_CHECKLIST = "defaut_checklist", "Défaut de sécurité signalé"
    INCIDENT = "incident", "Incident"
    STOCK_BAS = "stock_bas", "Stock de pièces bas"
    VEHICULE_LIBERE = "vehicule_libere", "Véhicule libéré"
    PENURIE = "penurie", "Pénurie de véhicule ou de chauffeur"
    RETARD_PREVU = "retard_prevu", "Risque de retard"
    SEUIL_CRITIQUE = "seuil_critique", "Seuil critique dépassé"
    ECHEANCE = "echeance", "Échéance proche"
    INFRACTION = "infraction", "Infraction grave"
    FATIGUE = "fatigue", "Fatigue du conducteur"
    RELAIS = "relais", "Relais de conducteur"
    COLIS = "colis", "Colis"
    CLOTURE_CAISSE = "cloture_caisse", "Clôture de caisse"
    NOTE_SERVICE = "note_service", "Note de service"
    LIGNE = "ligne", "Ligne fermée ou rouverte"
    DEMANDE_LIGNE = "demande_ligne", "Demande sur une ligne"
    REAFFECTATION = "reaffectation", "Véhicule réaffecté à une autre gare"
    INVESTISSEMENT = "investissement", "Investissement"
    COMPTE = "compte", "Compte d'agent"
    ENTRETIEN = "entretien", "Entretien préventif"
    ORDRE_REPARATION = "ordre_reparation", "Ordre de réparation"
    DEMANDE_PIECE = "demande_piece", "Demande de pièce"
    RENOUVELLEMENT = "renouvellement", "Renouvellement de véhicule"
    MESSAGE = "message", "Message de la gare"
    AGENDA = "agenda", "Agenda de la direction"
    BUDGET = "budget", "Budget"
    PAIEMENT = "paiement", "Paiement à effectuer"
    FORMATION = "formation", "Formation obligatoire"
    CONTRAT = "contrat", "Contrat de travail"
    CONGE = "conge", "Congé"
    DOLEANCE = "doleance", "Médiation sociale"
    LITIGE = "litige", "Litige social"
    SINISTRE = "sinistre", "Sinistre"
    AUTRE = "autre", "Autre"


class GraviteAlerte(models.TextChoices):
    INFO = "info", "Information"
    ATTENTION = "attention", "Attention"
    CRITIQUE = "critique", "Critique"


class Alerte(models.Model):
    """Message automatique d'un pôle vers les pôles concernés par une action.

    Une alerte vise des **rôles** (tous les agents de la compagnie ayant ce poste) et/ou des **agents** précis
    (par exemple le chef de la gare de départ du car concerné). Chaque destinataire la marque lue pour lui-même.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="alertes")
    type = models.CharField(max_length=30, choices=TypeAlerte.choices, default=TypeAlerte.AUTRE)
    gravite = models.CharField(max_length=10, choices=GraviteAlerte.choices, default=GraviteAlerte.INFO)
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    roles_destinataires = models.JSONField(default=list, blank=True)
    destinataires = models.ManyToManyField(User, blank=True, related_name="alertes_recues")
    # Objet à l'origine de l'alerte, pour y renvoyer (« billetterie.depart », « 12 »).
    objet_type = models.CharField(max_length=100, blank=True)
    objet_id = models.CharField(max_length=64, blank=True)
    cree_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cree_le = models.DateTimeField(default=timezone.now, db_index=True)
    # Clé d'unicité pour les alertes générées automatiquement : la même situation ne prévient pas dix fois.
    cle = models.CharField(max_length=120, null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-cree_le", "-id"]
        indexes = [models.Index(fields=["company", "-cree_le"], name="alerte_company_date")]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "cle"], condition=models.Q(cle__isnull=False), name="alerte_cle_unique_par_compagnie"
            )
        ]

    def __str__(self):
        return f"[{self.gravite}] {self.titre}"


class LectureAlerte(models.Model):
    alerte = models.ForeignKey(Alerte, on_delete=models.CASCADE, related_name="lectures")
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alertes_lues")
    lu_le = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alerte", "utilisateur"], name="lecture_alerte_unique")
        ]
