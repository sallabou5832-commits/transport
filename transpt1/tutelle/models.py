import hashlib
import secrets

from django.db import models
from django.utils import timezone

from core.models import Company


class TypeFlux(models.TextChoices):
    SECURITE = "securite", "Sécurité"
    FLUIDITE = "fluidite", "Fluidité"
    CONFORMITE = "conformite", "Conformité"
    TRAFIC_AGREGE = "trafic_agrege", "Trafic agrégé"


class DirectionFlux(models.TextChoices):
    VERS_TUTELLE = "vers_tutelle", "Vers la tutelle"
    VERS_COMPAGNIE = "vers_compagnie", "Vers la compagnie"


class StatutFlux(models.TextChoices):
    ENVOYE = "envoye", "Envoyé"
    RECU = "recu", "Reçu"
    TRAITE = "traite", "Traité"


class FluxTutelle(models.Model):
    """Un échange de données avec le Ministère des Transports et les organismes dépendants (OSER, AMUGA, OFT), dans
    un sens ou dans l'autre.

    Rien ici ne parle à un vrai système du ministère : le flux est généré et stocké côté compagnie, prêt à être
    transmis (ou à avoir été reçu) le jour où l'intégration existe (voir le paquet `tutelle` et son cahier des
    charges). `contenu` porte les données propres à chaque type de flux — jamais de schéma unique imposé, le
    ministère et ses organismes n'attendent pas la même chose d'une remontée de sécurité que d'une norme de
    conformité.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="flux_tutelle")
    type = models.CharField(max_length=20, choices=TypeFlux.choices)
    direction = models.CharField(max_length=20, choices=DirectionFlux.choices)
    contenu = models.JSONField(default=dict, blank=True)
    statut = models.CharField(max_length=10, choices=StatutFlux.choices)
    date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "flux avec la tutelle"
        verbose_name_plural = "flux avec la tutelle"
        indexes = [models.Index(fields=["company", "-date"], name="flux_tutelle_company_date")]

    def __str__(self):
        return f"{self.get_type_display()} ({self.get_direction_display()}) — {self.company}"


class CompteTutelle(models.Model):
    """Un compte côté Ministère des Transports ou d'un organisme dépendant (OSER, AMUGA, OFT), authentifié par clé
    d'API — un système séparé des comptes internes d'une compagnie (`core.User`) : il ne dépend d'aucune compagnie
    (il les voit toutes), et un jeton JWT de compte interne ne l'authentifie jamais (voir `tutelle.authentication`).

    La clé n'est jamais stockée en clair, seule son empreinte l'est (comme un mot de passe) : `creer()` est le seul
    moyen de l'obtenir, une fois, à la création.
    """

    nom = models.CharField(max_length=200)
    cle_hachee = models.CharField(max_length=64, unique=True, editable=False)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(default=timezone.now)
    derniere_utilisation = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "compte tutelle"
        verbose_name_plural = "comptes tutelle"

    def __str__(self):
        return self.nom

    @staticmethod
    def hacher(cle_en_clair):
        return hashlib.sha256(cle_en_clair.encode()).hexdigest()

    @classmethod
    def creer(cls, nom):
        """Crée un compte tutelle et renvoie `(compte, cle_en_clair)` : la clé en clair n'est jamais visible après
        cet appel (voir `tutelle/management/commands/creer_compte_tutelle.py`)."""
        cle_en_clair = secrets.token_urlsafe(32)
        compte = cls.objects.create(nom=nom, cle_hachee=cls.hacher(cle_en_clair))
        return compte, cle_en_clair

    # Duck-typing attendu par Django/DRF (`request.user.is_authenticated`) : voir `tutelle.authentication`. Un
    # compte tutelle authentifié est toujours actif (un compte désactivé est rejeté avant, à l'authentification).
    @property
    def is_authenticated(self):
        return True
