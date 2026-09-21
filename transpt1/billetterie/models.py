from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import Company
from reseau.models import Ligne, Vehicule


class DepartStatut(models.TextChoices):
    PLANIFIE = "planifie", "Planifié"
    EN_COURS = "en_cours", "En cours"
    TERMINE = "termine", "Terminé"


class Depart(models.Model):
    ligne = models.ForeignKey(Ligne, on_delete=models.PROTECT, related_name="departs")
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="departs")
    chauffeur = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="departs_conduits"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="departs")
    date_heure = models.DateTimeField()
    places_vendues = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=20, choices=DepartStatut.choices, default=DepartStatut.PLANIFIE
    )

    class Meta:
        ordering = ["-date_heure"]
        # Les tableaux de bord et le planning filtrent par compagnie et par jour.
        indexes = [models.Index(fields=["company", "date_heure"], name="depart_company_date_heure")]

    def __str__(self):
        return f"{self.ligne} - {self.date_heure:%Y-%m-%d %H:%M}"

    @property
    def places_restantes(self):
        return self.vehicule.capacite - self.places_vendues

    @property
    def places_reservees(self):
        """Places mises de côté (réservations hors ligne actives), pas encore vendues."""
        annotee = getattr(self, "_places_reservees", None)  # posée par DepartViewSet (évite N+1)
        if annotee is not None:
            return annotee
        return (
            self.reservations_hors_ligne.filter(expire_le__gt=timezone.now()).aggregate(
                total=models.Sum("places")
            )["total"]
            or 0
        )

    @property
    def places_disponibles(self):
        """Places qu'un guichetier SANS réservation peut vendre maintenant."""
        return max(0, self.places_restantes - self.places_reservees)


class ModePaiement(models.TextChoices):
    ESPECES = "especes", "Espèces"
    MOBILE_MONEY = "mobile_money", "Mobile money"


class StatutTicket(models.TextChoices):
    VALIDE = "valide", "Valide"
    ANNULE = "annule", "Annulé"


class Ticket(models.Model):
    depart = models.ForeignKey(Depart, on_delete=models.PROTECT, related_name="tickets")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="tickets")
    passager_nom = models.CharField(max_length=255)
    passager_telephone = models.CharField(max_length=30)
    prix = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    mode_paiement = models.CharField(max_length=20, choices=ModePaiement.choices)
    vendu_par = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="tickets_vendus"
    )
    date_vente = models.DateTimeField(auto_now_add=True)
    # Clé fournie par le client (en-tête Idempotency-Key) : rejouer la même vente,
    # par exemple après une coupure réseau, ne crée pas un second ticket.
    cle_idempotence = models.CharField(max_length=64, null=True, blank=True, editable=False)

    # Un ticket vendu ne se modifie ni ne se supprime jamais : une erreur se corrige par une annulation, qui garde
    # le ticket, dit qui l'a annulé, quand et pourquoi, libère la place et sort la vente des recettes.
    statut = models.CharField(
        max_length=10, choices=StatutTicket.choices, default=StatutTicket.VALIDE, db_index=True
    )
    annule_par = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets_annules"
    )
    annule_le = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date_vente"]
        indexes = [
            models.Index(fields=["company", "date_vente"], name="ticket_company_date_vente"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["vendu_par", "cle_idempotence"],
                condition=models.Q(cle_idempotence__isnull=False),
                name="ticket_cle_idempotence_unique_par_vendeur",
            )
        ]

    def __str__(self):
        return f"Ticket {self.passager_nom} - {self.depart}"


class ReservationHorsLigne(models.Model):
    """Places mises de côté pour un guichetier afin qu'il puisse vendre hors ligne.

    Sans réseau, un guichetier ignore les ventes des autres : rien ne l'empêcherait de
    vendre une place déjà prise, et le serveur refuserait la vente à la synchronisation
    alors que le voyageur a payé. En réservant d'avance ces places (tant qu'il a du réseau),
    ses ventes hors ligne sont garanties. Invariant, tenu sous verrou du départ :
    places vendues + places réservées actives <= capacité du véhicule.
    """

    depart = models.ForeignKey(Depart, on_delete=models.CASCADE, related_name="reservations_hors_ligne")
    guichetier = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="reservations_hors_ligne"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="reservations_hors_ligne")
    # Places encore réservées : diminue à chaque vente du guichetier sur ce départ.
    places = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    expire_le = models.DateTimeField()
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "réservation hors ligne"
        verbose_name_plural = "réservations hors ligne"
        constraints = [
            models.UniqueConstraint(
                fields=["depart", "guichetier"], name="reservation_unique_par_depart_et_guichetier"
            ),
            models.CheckConstraint(condition=models.Q(places__gte=1), name="reservation_places_positives"),
        ]

    def __str__(self):
        return f"{self.places} place(s) hors ligne pour {self.guichetier} sur {self.depart}"
