"""Une compagnie qui a déjà son logiciel de billetterie peut le garder : elle choisit son mode de billetterie, et les ventes
de son logiciel arrivent ici par une API (clé d'API de la compagnie) ou par l'import d'un fichier. Elles deviennent de vrais
billets (`billetterie.Ticket`) : places, recettes, tableaux de bord et contrôle à bord les voient comme les autres."""

import hashlib
import secrets

from django.db import models
from django.utils import timezone

from core.models import Company, User


class ModeBilletterie(models.TextChoices):
    INTEGRE = "integre", "Intégrée : le module de billetterie du logiciel"
    EXTERNE = "externe", "Externe : le logiciel de billetterie de la compagnie"
    MIXTE = "mixte", "Mixte : les deux à la fois"


class ReglageBilletterie(models.Model):
    """Le mode de billetterie de la compagnie. Sans réglage, la billetterie est intégrée (le comportement du socle)."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="reglage_billetterie")
    mode = models.CharField(max_length=10, choices=ModeBilletterie.choices, default=ModeBilletterie.INTEGRE)
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "mode de billetterie"
        verbose_name_plural = "modes de billetterie"

    def __str__(self):
        return f"Billetterie de {self.company} : {self.get_mode_display()}"


PREFIXE_CLE = "lb_"


class CleLienBilletterie(models.Model):
    """La clé d'API qu'un logiciel de billetterie présente pour lire les départs de la compagnie et lui envoyer ses ventes.

    Elle n'ouvre que les routes du lien (voir `lien_billetterie.authentication`) et une seule compagnie. Comme un mot de
    passe, elle n'est jamais stockée en clair : `creer()` est le seul moyen de la voir, une fois."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="cles_lien_billetterie")
    logiciel = models.CharField(max_length=100)  # le nom du logiciel relié, écrit sur chaque billet qu'il envoie
    debut_cle = models.CharField(max_length=12, editable=False)  # pour reconnaître la clé dans la liste sans la montrer
    cle_hachee = models.CharField(max_length=64, unique=True, editable=False)
    active = models.BooleanField(default=True)
    creee_par = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    creee_le = models.DateTimeField(default=timezone.now)
    revoquee_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    revoquee_le = models.DateTimeField(null=True, blank=True)
    derniere_utilisation = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creee_le", "-id"]
        verbose_name = "clé du lien de billetterie"
        verbose_name_plural = "clés du lien de billetterie"

    def __str__(self):
        return f"{self.logiciel} ({self.debut_cle}…) — {self.company}"

    @staticmethod
    def hacher(cle_en_clair):
        return hashlib.sha256(cle_en_clair.encode()).hexdigest()

    @classmethod
    def creer(cls, *, company, logiciel, par):
        """Crée une clé et renvoie `(clé, clé_en_clair)` : la clé en clair n'est plus jamais visible ensuite."""
        cle_en_clair = PREFIXE_CLE + secrets.token_urlsafe(32)
        cle = cls.objects.create(
            company=company, logiciel=logiciel, debut_cle=cle_en_clair[:10], cle_hachee=cls.hacher(cle_en_clair), creee_par=par
        )
        return cle, cle_en_clair

    # Ce que Django et DRF attendent de `request.user` : une clé authentifiée est toujours active (une clé révoquée est
    # refusée avant, à l'authentification).
    @property
    def is_authenticated(self):
        return True


class ImportVentes(models.Model):
    """Un fichier de ventes déposé (export du logiciel de la compagnie), avec le compte rendu de chaque ligne."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="imports_ventes")
    logiciel = models.CharField(max_length=100)
    fichier = models.CharField(max_length=255)  # le nom du fichier déposé ; son contenu n'est pas conservé
    depose_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    depose_le = models.DateTimeField(default=timezone.now)
    lignes = models.PositiveIntegerField(default=0)
    creees = models.PositiveIntegerField(default=0)
    deja_recues = models.PositiveIntegerField(default=0)
    refusees = models.PositiveIntegerField(default=0)
    # [{ligne, reference, statut, ticket?, erreurs?}] : ce qui a été fait de chaque ligne du fichier, et pourquoi.
    rapport = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-depose_le", "-id"]
        verbose_name = "import de ventes"
        verbose_name_plural = "imports de ventes"

    def __str__(self):
        return f"Import {self.fichier} ({self.logiciel}) — {self.company}"
