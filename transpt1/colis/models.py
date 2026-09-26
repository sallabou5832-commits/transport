import secrets
from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MinValueValidator
from django.db import models

from billetterie.models import Depart, ModePaiement, Ticket
from core.models import Company

# Le code de retrait est envoyé au destinataire par SMS/WhatsApp : court, lisible, sans caractère ambigu (0/O, 1/I).
ALPHABET_CODE = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
LONGUEUR_CODE = 6
# Au-delà, le retrait est verrouillé : seul un responsable renvoie un nouveau code (voir `renvoyer-code`).
MAX_TENTATIVES_CODE = 5


def generer_code():
    return "".join(secrets.choice(ALPHABET_CODE) for _ in range(LONGUEUR_CODE))


def normaliser_code(code):
    return str(code or "").strip().upper().replace("-", "").replace(" ", "")


class TypeColis(models.TextChoices):
    BAGAGE = "bagage", "Bagage"
    COLIS = "colis", "Colis"


class StatutColis(models.TextChoices):
    ENREGISTRE = "enregistre", "Enregistré"
    CHARGE = "charge", "Chargé"
    ARRIVE = "arrive", "Arrivé"
    RETIRE = "retire", "Retiré"
    ANNULE = "annule", "Annulé"


class Colis(models.Model):
    """Un bagage ou un colis confié à un départ, suivi de bout en bout : enregistré, chargé, arrivé, retiré.

    Il peut être lié au billet d'un voyageur (son bagage) ou voyager seul (un envoi). Le client n'a pas accès au
    logiciel : son code de retrait et chaque étape lui sont envoyés par SMS ou WhatsApp. Le code n'est jamais stocké
    en clair (seule son empreinte l'est) ni renvoyé par l'API : celui qui remet le colis le saisit, le système le vérifie.
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="colis")
    depart = models.ForeignKey(Depart, on_delete=models.PROTECT, related_name="colis")
    ticket = models.ForeignKey(Ticket, null=True, blank=True, on_delete=models.SET_NULL, related_name="colis")
    type_colis = models.CharField(max_length=10, choices=TypeColis.choices, default=TypeColis.COLIS)
    description = models.CharField(max_length=255)
    poids_kg = models.DecimalField(
        max_digits=7, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))], help_text="Poids estimé."
    )
    valeur_declaree = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    # Frais de fret encaissés à l'enregistrement (espèces ou mobile money, comme un billet).
    frais = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    mode_paiement = models.CharField(max_length=20, choices=ModePaiement.choices, blank=True)

    expediteur_nom = models.CharField(max_length=255)
    expediteur_telephone = models.CharField(max_length=30, blank=True)
    destinataire_nom = models.CharField(max_length=255)
    destinataire_telephone = models.CharField(max_length=30)

    statut = models.CharField(max_length=12, choices=StatutColis.choices, default=StatutColis.ENREGISTRE, db_index=True)
    code_retrait_hash = models.CharField(max_length=128, editable=False)
    tentatives_code = models.PositiveSmallIntegerField(default=0, editable=False)

    enregistre_par = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="colis_enregistres")
    enregistre_le = models.DateTimeField(auto_now_add=True)
    charge_par = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="colis_charges"
    )
    charge_le = models.DateTimeField(null=True, blank=True)
    arrive_le = models.DateTimeField(null=True, blank=True)
    retire_par = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="colis_remis"
    )
    retire_le = models.DateTimeField(null=True, blank=True)
    # Qui est reparti avec le colis (le destinataire, ou la personne qu'il a mandatée).
    retire_par_nom = models.CharField(max_length=255, blank=True)
    annule_par = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="colis_annules"
    )
    annule_le = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.CharField(max_length=255, blank=True)

    # Comme un billet, un enregistrement se rejoue sans doublon (coupure réseau, synchronisation du mobile).
    cle_idempotence = models.CharField(max_length=64, null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-enregistre_le", "-id"]
        verbose_name = "colis"
        verbose_name_plural = "colis"
        indexes = [
            models.Index(fields=["company", "statut"], name="colis_company_statut"),
            models.Index(fields=["depart", "statut"], name="colis_depart_statut"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["enregistre_par", "cle_idempotence"],
                condition=models.Q(cle_idempotence__isnull=False),
                name="colis_cle_idempotence_unique_par_agent",
            ),
            models.CheckConstraint(condition=models.Q(poids_kg__gt=0), name="colis_poids_positif"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.description}"

    @property
    def reference(self):
        return f"COL-{self.pk:06d}" if self.pk else "COL-nouveau"

    @property
    def gare_arrivee(self):
        return self.depart.ligne.gare_arrivee

    @property
    def code_verrouille(self):
        return self.tentatives_code >= MAX_TENTATIVES_CODE

    def definir_code(self, code):
        self.code_retrait_hash = make_password(normaliser_code(code))
        self.tentatives_code = 0

    def code_correspond(self, code):
        return check_password(normaliser_code(code), self.code_retrait_hash)
