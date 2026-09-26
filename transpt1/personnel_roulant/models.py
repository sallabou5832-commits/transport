from django.db import models
from django.utils import timezone

from billetterie.models import Depart
from core.models import Company
from reseau.models import Vehicule, VehiculeStatut

# Items de la checklist dont un défaut rend le véhicule dangereux à conduire.
# Le carburant, par exemple, n'en fait pas partie : un plein bas est un
# problème logistique, pas un problème de sécurité.
ITEMS_SECURITE = {"pneus", "freins", "direction", "eclairage", "ceintures", "extincteur"}
# Ce que le conducteur qui reprend un trajet constate, un à un, avant de repartir.
ITEMS_REPRISE = ("pneus", "freins", "carburant", "eclairage", "direction", "ceintures")


class FeuilleDeRoute(models.Model):
    depart = models.OneToOneField(Depart, on_delete=models.PROTECT, related_name="feuille_de_route")
    chauffeur = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="feuilles_de_route"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="feuilles_de_route")
    heure_depart_prevue = models.DateTimeField()
    heure_depart_reelle = models.DateTimeField(null=True, blank=True)
    heure_arrivee_prevue = models.DateTimeField(null=True, blank=True)
    heure_arrivee_reelle = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-heure_depart_prevue"]
        indexes = [models.Index(fields=["company", "heure_depart_prevue"], name="feuille_company_depart_prevu")]

    def __str__(self):
        return f"Feuille de route {self.depart} ({self.chauffeur})"

    @property
    def peut_demarrer(self):
        if self.heure_depart_reelle is not None:
            return False
        if self.depart.vehicule.statut == VehiculeStatut.BLOQUE_SECURITE:
            return False
        if self.checklist_items.filter(etat=EtatChecklist.DEFAUT, item__in=ITEMS_SECURITE).exists():
            return False
        return True


class EtatChecklist(models.TextChoices):
    OK = "ok", "OK"
    DEFAUT = "defaut", "Défaut"


class ChecklistDepart(models.Model):
    feuille_de_route = models.ForeignKey(
        FeuilleDeRoute, on_delete=models.CASCADE, related_name="checklist_items"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="checklist_items")
    item = models.CharField(max_length=100)
    etat = models.CharField(max_length=10, choices=EtatChecklist.choices)
    commentaire = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "item de checklist"
        verbose_name_plural = "items de checklist"

    def __str__(self):
        return f"{self.item} - {self.etat}"

    @property
    def est_item_securite(self):
        return self.item.strip().lower() in ITEMS_SECURITE

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.etat == EtatChecklist.DEFAUT and self.est_item_securite:
            vehicule = self.feuille_de_route.depart.vehicule
            if vehicule.statut != VehiculeStatut.BLOQUE_SECURITE:
                vehicule.statut = VehiculeStatut.BLOQUE_SECURITE
                vehicule.save(update_fields=["statut"])
                self._alerter_du_blocage(vehicule)

    def _alerter_du_blocage(self, vehicule):
        """Le blocage d'un car concerne le QHSE, l'atelier, la régulation et la gare de départ."""
        from alertes.models import GraviteAlerte, TypeAlerte
        from alertes.services import alerter, chef_de_gare_du_depart
        from core.models import Role

        depart = self.feuille_de_route.depart
        alerter(
            self.company,
            type=TypeAlerte.DEFAUT_CHECKLIST,
            gravite=GraviteAlerte.CRITIQUE,
            titre=f"Défaut de sécurité « {self.item} » : {vehicule.immatriculation} bloqué",
            message=(
                f"Défaut « {self.item} » signalé sur la checklist du départ {depart}. Le véhicule est bloqué : "
                f"il ne peut pas partir avant sa réparation. {self.commentaire}"
            ).strip(),
            roles=[Role.QHSE, Role.CHEF_ATELIER, Role.DIRECTEUR_TECHNIQUE, Role.CHEF_LIGNE],
            destinataires=[chef_de_gare_du_depart(depart)],
            objet=depart,
        )


class BlocageSecurite(models.Model):
    """Blocage du départ d'un véhicule décidé par le QHSE, avec le motif, l'auteur et la levée éventuelle.

    Il s'ajoute au blocage automatique par la checklist : le QHSE peut immobiliser un car sans attendre que le
    chauffeur coche un défaut. Tant que le blocage est actif, le véhicule reste `bloque_securite`."""

    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="blocages_securite")
    depart = models.ForeignKey(
        Depart, null=True, blank=True, on_delete=models.SET_NULL, related_name="blocages_securite"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="blocages_securite")
    motif = models.CharField(max_length=255)
    pose_par = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="blocages_poses")
    pose_le = models.DateTimeField(default=timezone.now)
    leve_par = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="blocages_leves"
    )
    leve_le = models.DateTimeField(null=True, blank=True)
    motif_levee = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-pose_le"]
        verbose_name = "blocage de sécurité"
        verbose_name_plural = "blocages de sécurité"
        constraints = [
            # Un seul blocage actif par véhicule : on ne bloque pas deux fois un car déjà arrêté.
            models.UniqueConstraint(
                fields=["vehicule"], condition=models.Q(leve_le__isnull=True), name="un_blocage_actif_par_vehicule"
            )
        ]

    def __str__(self):
        return f"Blocage {self.vehicule} : {self.motif}"

    @property
    def est_actif(self):
        return self.leve_le is None


class TypeIncident(models.TextChoices):
    PANNE = "panne", "Panne"
    ACCIDENT = "accident", "Accident"
    RETARD = "retard", "Retard"
    CARGAISON = "cargaison", "Anomalie de cargaison"
    AUTRE = "autre", "Autre"


class GraviteIncident(models.TextChoices):
    FAIBLE = "faible", "Faible"
    MOYENNE = "moyenne", "Moyenne"
    GRAVE = "grave", "Grave"


class StatutIncident(models.TextChoices):
    OUVERT = "ouvert", "Ouvert"
    TRAITE = "traite", "Traité"


class Incident(models.Model):
    feuille_de_route = models.ForeignKey(
        FeuilleDeRoute,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
    )
    vehicule = models.ForeignKey(Vehicule, on_delete=models.PROTECT, related_name="incidents")
    chauffeur = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="incidents_signales"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="incidents")
    type_incident = models.CharField(max_length=20, choices=TypeIncident.choices)
    description = models.TextField()
    date = models.DateTimeField(default=timezone.now)
    gravite = models.CharField(max_length=10, choices=GraviteIncident.choices)
    statut = models.CharField(
        max_length=10, choices=StatutIncident.choices, default=StatutIncident.OUVERT
    )
    # Où l'incident a été signalé : donné par l'appareil du chauffeur, ou, à défaut, la dernière position connue du car.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["company", "statut", "date"], name="incident_company_statut_date")]

    def __str__(self):
        return f"Incident {self.type_incident} - {self.vehicule} ({self.gravite})"


class PositionVehicule(models.Model):
    """Un relevé GPS d'un car en route, envoyé par l'appareil de son conducteur (même hors ligne : `releve_le` est l'heure du
    relevé, pas celle de l'envoi). Le suivi appartient au véhicule et à la feuille de route, pas au conducteur : au relais,
    il continue tout seul sur le nouveau conducteur."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="positions")
    vehicule = models.ForeignKey(Vehicule, on_delete=models.CASCADE, related_name="positions")
    feuille_de_route = models.ForeignKey(FeuilleDeRoute, on_delete=models.CASCADE, related_name="positions")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    vitesse_kmh = models.PositiveSmallIntegerField(null=True, blank=True)
    releve_le = models.DateTimeField(default=timezone.now)
    releve_par = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-releve_le", "-id"]
        verbose_name = "position d'un véhicule"
        verbose_name_plural = "positions des véhicules"
        indexes = [
            models.Index(fields=["vehicule", "-releve_le"], name="position_vehicule_date"),
            models.Index(fields=["company", "-releve_le"], name="position_company_date"),
            # Couvre `suivi.dernieres_positions` : `.filter(feuille_de_route_id__in=...).order_by("feuille_de_route_id",
            # "-releve_le", "-id").distinct("feuille_de_route_id")` — sans lui, PostgreSQL trie la table entière (ou le
            # sous-ensemble filtré) au lieu de sauter directement à la dernière ligne de chaque feuille de route.
            models.Index(fields=["feuille_de_route", "-releve_le", "-id"], name="position_feuille_date"),
        ]

    def __str__(self):
        return f"{self.vehicule} en {self.latitude},{self.longitude} ({self.releve_le:%H:%M})"


class PausePrise(models.Model):
    """Une pause du conducteur : elle remet à zéro le temps de conduite continue (alerte de fatigue)."""

    feuille_de_route = models.ForeignKey(FeuilleDeRoute, on_delete=models.CASCADE, related_name="pauses")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="+")
    chauffeur = models.ForeignKey("core.User", on_delete=models.CASCADE, related_name="pauses")
    debut = models.DateTimeField(default=timezone.now)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-debut"]
        verbose_name = "pause"
        verbose_name_plural = "pauses"
        constraints = [
            # Une seule pause ouverte par feuille de route : on ne commence pas une pause déjà commencée.
            models.UniqueConstraint(
                fields=["feuille_de_route"], condition=models.Q(fin__isnull=True), name="une_pause_ouverte_par_feuille"
            )
        ]


class Relais(models.Model):
    """Le transfert d'un trajet d'un conducteur à un autre, en route : la feuille de route change de main, avec l'état du
    véhicule au moment du transfert. Le lieu et l'heure préviennent le nouveau conducteur, la régulation et la gare."""

    feuille_de_route = models.ForeignKey(FeuilleDeRoute, on_delete=models.CASCADE, related_name="relais")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="+")
    ancien_chauffeur = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="relais_cedes")
    nouveau_chauffeur = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="relais_pris")
    lieu = models.CharField(max_length=255)
    effectue_le = models.DateTimeField(default=timezone.now)
    effectue_par = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Photographie de l'état du véhicule transmis : statut, items de checklist en défaut, incidents ouverts.
    etat_vehicule = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-effectue_le"]
        verbose_name = "relais"
        verbose_name_plural = "relais"

    def __str__(self):
        return f"Relais {self.ancien_chauffeur} → {self.nouveau_chauffeur} à {self.lieu}"


class ChecklistReprise(models.Model):
    """L'état du car constaté par le conducteur qui reprend le trajet, item par item. Un défaut de sécurité prévient aussitôt le QHSE, la
    régulation et l'atelier : le car est déjà en route, il ne se « bloque » pas comme au départ, mais tout le monde le sait."""

    relais = models.ForeignKey(Relais, on_delete=models.CASCADE, related_name="checklist_reprise")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="+")
    item = models.CharField(max_length=100)
    etat = models.CharField(max_length=10, choices=EtatChecklist.choices)
    commentaire = models.CharField(max_length=500, blank=True)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        verbose_name = "item de checklist de reprise"
        verbose_name_plural = "items de checklist de reprise"
        constraints = [models.UniqueConstraint(fields=["relais", "item"], name="reprise_un_etat_par_item")]

    def __str__(self):
        return f"{self.item} - {self.etat} (reprise)"


class ControleLigne(models.Model):
    """Un contrôle à bord par un contrôleur de ligne : les billets vérifiés, le nombre de voyageurs et la charge constatés, le
    rapport généré à la clôture, et une éventuelle infraction grave (qui alerte directement la direction et le QHSE)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="controles")
    controleur = models.ForeignKey("core.User", on_delete=models.PROTECT, related_name="controles_effectues")
    feuille_de_route = models.ForeignKey(FeuilleDeRoute, on_delete=models.PROTECT, related_name="controles")
    debut = models.DateTimeField(default=timezone.now)
    cloture_le = models.DateTimeField(null=True, blank=True)
    passagers_constates = models.PositiveIntegerField(null=True, blank=True)
    charge_constatee_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    commentaire = models.TextField(blank=True)
    infraction_grave = models.BooleanField(default=False)
    motif_infraction = models.CharField(max_length=255, blank=True)
    # Généré à la clôture : billets, voyageurs et charge comparés à ce qui a été enregistré au départ, anomalies relevées.
    rapport = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-debut", "-id"]
        verbose_name = "contrôle de ligne"
        verbose_name_plural = "contrôles de ligne"
        indexes = [models.Index(fields=["company", "-debut"], name="controle_company_debut")]

    def __str__(self):
        return f"Contrôle {self.feuille_de_route} par {self.controleur}"

    @property
    def est_ouvert(self):
        return self.cloture_le is None


class ResultatVerification(models.TextChoices):
    VALIDE = "valide", "Billet valide"
    DEJA_UTILISE = "deja_utilise", "Billet déjà utilisé"
    ANNULE = "annule", "Billet annulé"
    INCONNU = "inconnu", "Billet inconnu"
    AUTRE_DEPART = "autre_depart", "Billet d'un autre départ"
    DEPART_TERMINE = "depart_termine", "Départ terminé"


class VerificationTicket(models.Model):
    controle = models.ForeignKey(ControleLigne, on_delete=models.CASCADE, related_name="verifications")
    code = models.CharField(max_length=32)
    resultat = models.CharField(max_length=20, choices=ResultatVerification.choices)
    ticket = models.ForeignKey("billetterie.Ticket", null=True, blank=True, on_delete=models.SET_NULL, related_name="verifications")
    verifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["verifie_le", "id"]
