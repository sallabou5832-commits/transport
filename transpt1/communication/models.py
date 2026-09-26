from django.db import models

from core.models import Company, User
from reseau.models import Gare


class NoteService(models.Model):
    """Note de service diffusée aux postes concernés, sans passer par le PDG (cahier des charges : secrétaire général). Chaque
    poste visé la reçoit dans sa cloche d'alertes ; la note reste consultable ensuite."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="notes_service")
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    roles_destinataires = models.JSONField(default=list)
    urgente = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]
        verbose_name = "note de service"
        verbose_name_plural = "notes de service"

    def __str__(self):
        return self.titre


class PorteeMessage(models.TextChoices):
    EQUIPE = "equipe", "Mon équipe"
    APPROCHE = "approche", "Chauffeurs en approche"
    LES_DEUX = "les_deux", "Équipe et chauffeurs en approche"


class MessageDirect(models.Model):
    """Message direct du chef de gare à son équipe locale et/ou aux chauffeurs dont le car arrive à sa gare."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="messages_directs")
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    gare = models.ForeignKey(Gare, on_delete=models.PROTECT, related_name="messages_directs")
    portee = models.CharField(max_length=10, choices=PorteeMessage.choices)
    texte = models.TextField(max_length=500)
    destinataires = models.ManyToManyField(User, related_name="messages_directs_recus", blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]

    def __str__(self):
        return f"{self.gare.nom} : {self.texte[:40]}"


class EvenementAgenda(models.Model):
    """Rendez-vous de l'agenda partagé de la direction : réunions, visites, échéances. Les postes invités sont alertés."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="evenements_agenda")
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    titre = models.CharField(max_length=200)
    debut = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    lieu = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    participants = models.JSONField(default=list, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["debut", "id"]
        verbose_name = "événement de l'agenda"
        verbose_name_plural = "événements de l'agenda"

    def __str__(self):
        return self.titre


class CategorieDocument(models.TextChoices):
    COURRIER = "courrier", "Courrier"
    CONTRAT = "contrat", "Contrat"
    RAPPORT = "rapport", "Rapport"
    DECISION = "decision", "Décision"
    PROCEDURE = "procedure", "Procédure"
    AUTRE = "autre", "Autre"


class DocumentArchive(models.Model):
    """Dossier administratif classé : ce qu'il est, où il se trouve (armoire, chemin, lien), et s'il est archivé. Le registre
    ne contient pas le fichier : il permet de le retrouver."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="archives")
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    titre = models.CharField(max_length=200)
    categorie = models.CharField(max_length=10, choices=CategorieDocument.choices, default=CategorieDocument.AUTRE)
    reference = models.CharField(max_length=100, blank=True)
    date_document = models.DateField()
    emplacement = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    mots_cles = models.CharField(max_length=200, blank=True)
    archive = models.BooleanField(default=False)
    archive_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_document", "-id"]
        verbose_name = "document archivé"
        verbose_name_plural = "documents archivés"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "reference"], condition=~models.Q(reference=""), name="archive_reference_unique_par_compagnie"
            )
        ]

    def __str__(self):
        return self.titre
