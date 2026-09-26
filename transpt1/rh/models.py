"""Ressources humaines : ce que le DRH tient (formations obligatoires, contrats, évaluations, discipline, congés, recrutement) et
le canal de médiation sociale que tout agent peut utiliser. Le dossier de l'agent lui-même vit dans `supports.DossierAgent`."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import Company, Role, User
from reseau.models import Gare

ROLES_DE_COMPAGNIE = [(valeur, libelle) for valeur, libelle in Role.choices if valeur != Role.SUPERADMIN]


# --- Formations obligatoires ------------------------------------------------------------------------------------------------


class ObligationFormation(models.Model):
    """Une formation ou un document obligatoire pour certains postes (permis, visite médicale, sécurité routière OSER, secourisme…) :
    le catalogue de la compagnie. Sans durée de validité, elle se passe une fois pour toutes."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="obligations_formation")
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    roles = models.JSONField(default=list, help_text="Les postes concernés.")
    validite_mois = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    preavis_jours = models.PositiveSmallIntegerField(default=60, help_text="Combien de jours avant l'échéance on prévient.")

    class Meta:
        ordering = ["nom"]
        constraints = [models.UniqueConstraint(fields=["company", "nom"], name="obligation_formation_unique")]

    def __str__(self):
        return self.nom


class FormationSuivie(models.Model):
    """Une session suivie (ou un document obtenu) par un agent. Renouveler, c'est enregistrer une nouvelle session : l'historique
    reste, la plus récente fait foi."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="formations_suivies")
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="formations_suivies")
    obligation = models.ForeignKey(ObligationFormation, on_delete=models.PROTECT, related_name="suivies")
    date_obtention = models.DateField()
    date_expiration = models.DateField(null=True, blank=True)
    organisme = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    saisi_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_obtention", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["agent", "obligation", "date_obtention"], name="formation_suivie_unique")
        ]

    def __str__(self):
        return f"{self.obligation} — {self.agent} ({self.date_obtention})"


# --- Dossier de l'agent : contrat, évaluations, discipline ---------------------------------------------------------------------


class TypeContrat(models.TextChoices):
    CDI = "cdi", "CDI"
    CDD = "cdd", "CDD"
    JOURNALIER = "journalier", "Journalier / occasionnel"
    STAGE = "stage", "Stage"


class ContratAgent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="contrats_agents")
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contrats")
    type = models.CharField(max_length=12, choices=TypeContrat.choices, default=TypeContrat.CDI)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_debut", "-id"]

    def __str__(self):
        return f"{self.get_type_display()} de {self.agent} depuis le {self.date_debut}"


class EvaluationAgent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="evaluations_agents")
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="evaluations")
    date = models.DateField()
    note = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    commentaire = models.TextField(blank=True)
    evaluateur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"Évaluation de {self.agent} ({self.note}/5)"


class TypeMesure(models.TextChoices):
    AVERTISSEMENT = "avertissement", "Avertissement"
    BLAME = "blame", "Blâme"
    MISE_A_PIED = "mise_a_pied", "Mise à pied"
    AUTRE = "autre", "Autre"


class MesureDisciplinaire(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="mesures_disciplinaires")
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mesures_disciplinaires")
    date = models.DateField()
    type = models.CharField(max_length=15, choices=TypeMesure.choices, default=TypeMesure.AVERTISSEMENT)
    motif = models.TextField()
    duree_jours = models.PositiveSmallIntegerField(null=True, blank=True)
    decidee_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_type_display()} : {self.agent} ({self.date})"


# --- Congés -----------------------------------------------------------------------------------------------------------------


class TypeConge(models.TextChoices):
    ANNUEL = "annuel", "Congé annuel"
    MALADIE = "maladie", "Maladie"
    FAMILLE = "famille", "Événement familial, maternité ou paternité"
    SANS_SOLDE = "sans_solde", "Sans solde"
    AUTRE = "autre", "Autre"


class StatutConge(models.TextChoices):
    EN_ATTENTE = "en_attente", "En attente"
    APPROUVE = "approuve", "Approuvé"
    REFUSE = "refuse", "Refusé"
    ANNULE = "annule", "Annulé"


class DemandeConge(models.Model):
    """Une demande de congé. Avant de la valider, le DRH voit l'effet sur le personnel disponible (`rh.conges`)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="demandes_conge")
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="demandes_conge")
    type = models.CharField(max_length=12, choices=TypeConge.choices, default=TypeConge.ANNUEL)
    debut = models.DateField()
    fin = models.DateField()
    motif = models.TextField(blank=True)
    statut = models.CharField(max_length=12, choices=StatutConge.choices, default=StatutConge.EN_ATTENTE)
    decide_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decide_le = models.DateTimeField(null=True, blank=True)
    motif_decision = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["debut", "id"]
        constraints = [models.CheckConstraint(condition=models.Q(fin__gte=models.F("debut")), name="conge_fin_apres_debut")]
        indexes = [models.Index(fields=["company", "debut"], name="conge_company_debut")]

    def __str__(self):
        return f"{self.get_type_display()} de {self.agent} du {self.debut} au {self.fin}"


# --- Recrutement --------------------------------------------------------------------------------------------------------------


class FicheDePoste(models.Model):
    """La fiche de poste d'un rôle de l'organigramme quand la compagnie a personnalisé la fiche type (voir `rh.fiches_types`)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="fiches_de_poste")
    role = models.CharField(max_length=32, choices=ROLES_DE_COMPAGNIE)
    intitule = models.CharField(max_length=200)
    missions = models.TextField()
    profil = models.TextField()
    conditions = models.TextField(blank=True)
    modifie_par = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role"]
        constraints = [models.UniqueConstraint(fields=["company", "role"], name="fiche_de_poste_unique")]

    def __str__(self):
        return self.intitule


class StatutOffre(models.TextChoices):
    OUVERTE = "ouverte", "Ouverte"
    POURVUE = "pourvue", "Pourvue"
    CLOTUREE = "cloturee", "Clôturée"


class OffreRecrutement(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="offres_recrutement")
    role = models.CharField(max_length=32, choices=ROLES_DE_COMPAGNIE)
    intitule = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text="Copie de la fiche de poste à l'ouverture de l'offre.")
    nombre_postes = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    gare = models.ForeignKey(Gare, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_limite = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=10, choices=StatutOffre.choices, default=StatutOffre.OUVERTE)
    cree_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]

    def __str__(self):
        return self.intitule


class StatutCandidature(models.TextChoices):
    RECUE = "recue", "Reçue"
    PRESELECTIONNEE = "preselectionnee", "Présélectionnée"
    ENTRETIEN = "entretien", "En entretien"
    RETENUE = "retenue", "Retenue"
    REFUSEE = "refusee", "Refusée"


class Candidature(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="candidatures")
    offre = models.ForeignKey(OffreRecrutement, on_delete=models.CASCADE, related_name="candidatures")
    nom = models.CharField(max_length=200)
    telephone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    source = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=16, choices=StatutCandidature.choices, default=StatutCandidature.RECUE)
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["offre_id", "cree_le", "id"]

    def __str__(self):
        return f"{self.nom} — {self.offre}"


# --- Médiation sociale -----------------------------------------------------------------------------------------------------


class GraviteDoleance(models.TextChoices):
    FAIBLE = "faible", "Faible"
    MOYENNE = "moyenne", "Moyenne"
    GRAVE = "grave", "Grave"
    CRITIQUE = "critique", "Critique"

    @classmethod
    def rang(cls, gravite):
        return [valeur for valeur, _ in cls.choices].index(gravite)


class OrigineDoleance(models.TextChoices):
    AGENT = "agent", "Un agent"
    SYNDICAT = "syndicat", "Un syndicat ou les délégués du personnel"


class StatutDoleance(models.TextChoices):
    DEPOSEE = "deposee", "Déposée"
    EN_MEDIATION = "en_mediation", "En médiation"
    RESOLUE = "resolue", "Résolue"
    SANS_SUITE = "sans_suite", "Classée sans suite"


class Doleance(models.Model):
    """Une doléance déposée dans le canal de médiation sociale, par un agent ou au nom d'un syndicat. Au-delà d'un seuil de gravité,
    le responsable juridique est prévenu d'un risque de litige social (`rh.mediation`)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="doleances")
    origine = models.CharField(max_length=10, choices=OrigineDoleance.choices, default=OrigineDoleance.AGENT)
    auteur = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="doleances")
    syndicat = models.CharField(max_length=200, blank=True)
    objet = models.CharField(max_length=200)
    description = models.TextField()
    gravite = models.CharField(max_length=10, choices=GraviteDoleance.choices, default=GraviteDoleance.MOYENNE)
    statut = models.CharField(max_length=12, choices=StatutDoleance.choices, default=StatutDoleance.DEPOSEE)
    litige_signale_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(default=timezone.now)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cree_le", "-id"]

    def __str__(self):
        return self.objet


class SuiviDoleance(models.Model):
    """Une étape de la médiation : ce que le DRH a fait ou dit, visible ou non de l'agent qui a déposé la doléance."""

    doleance = models.ForeignKey(Doleance, on_delete=models.CASCADE, related_name="suivis")
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    texte = models.TextField()
    visible_du_deposant = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cree_le", "id"]

    def __str__(self):
        return f"Suivi de « {self.doleance} »"
