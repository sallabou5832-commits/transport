from django.db import models
from django.utils import timezone

from configuration.regles import AisanceNumerique, DureeSession, NiveauAutomatisation, NiveauGamification
from core.models import Company, Role, User


class ConfigurationCompagnie(models.Model):
    """Le cadre de la compagnie, fixé par le PDG : aucun poste ne peut dépasser ces plafonds."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="configuration")
    automatisation_max = models.CharField(
        max_length=12, choices=NiveauAutomatisation.CHOIX, default=NiveauAutomatisation.AUTOMATIQUE
    )
    gamification_max = models.CharField(
        max_length=10, choices=NiveauGamification.CHOIX, default=NiveauGamification.COMPLET
    )
    # Accès aux comptes : la plus longue session permise (« rester connecté ») et le code court exigé sur le mobile.
    duree_session_max = models.CharField(
        max_length=12, choices=DureeSession.CHOIX, default=DureeSession.PLAFOND_PAR_DEFAUT
    )
    code_court_exige = models.BooleanField(default=False)
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "cadre de la compagnie"
        verbose_name_plural = "cadres des compagnies"

    def __str__(self):
        return f"Cadre de {self.company}"


class ReglementInterieur(models.Model):
    """Ce que la compagnie permet ou non à certains postes (voir `regles.REGLEMENT`), réglé par le PDG et, pour son pôle,
    par chaque directeur. Seules les règles réglées sont enregistrées : les autres suivent le défaut du socle."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="reglement_interieur")
    regles = models.JSONField(default=dict, blank=True)  # {code de `regles.REGLEMENT`: permis}
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "règlement intérieur"
        verbose_name_plural = "règlements intérieurs"

    def __str__(self):
        return f"Règlement intérieur de {self.company}"


class ConfigurationPoste(models.Model):
    """Les réglages d'un poste dans une compagnie, faits par l'échelon directement supérieur (ou le PDG). Une valeur
    vide (`null`) laisse le défaut du socle."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="configurations_postes")
    role = models.CharField(max_length=32, choices=[(r.value, r.label) for r in Role if r != Role.SUPERADMIN])
    niveau_automatisation = models.CharField(
        max_length=12, choices=NiveauAutomatisation.CHOIX, null=True, blank=True
    )
    niveau_gamification = models.CharField(max_length=10, choices=NiveauGamification.CHOIX, null=True, blank=True)
    # Codes de `regles.FONCTIONS` retirés à ce poste.
    fonctions_desactivees = models.JSONField(default=list, blank=True)
    prefere_vocal = models.BooleanField(default=False)
    # Faux : chaque agent du poste peut choisir lui-même son mode vocal (« Mes paramètres ») ; vrai : ce réglage s'impose.
    prefere_vocal_impose = models.BooleanField(default=False)
    # Durée de session réduite pour ce poste (jamais au-delà du plafond de la compagnie) ; vide : le plafond de la compagnie.
    duree_session_max = models.CharField(max_length=12, choices=DureeSession.CHOIX, null=True, blank=True)
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "configuration d'un poste"
        verbose_name_plural = "configurations des postes"
        constraints = [models.UniqueConstraint(fields=["company", "role"], name="configuration_poste_unique")]

    def __str__(self):
        return f"{self.role} ({self.company})"


class ConfigurationAgent(models.Model):
    """Ajustement pour un agent précis, qui tient compte de sa propre aisance avec le numérique et de sa préférence pour
    le mode vocal : le niveau d'un poste n'est pas forcément celui de chacun de ceux qui l'occupent."""

    agent = models.OneToOneField(User, on_delete=models.CASCADE, related_name="configuration_agent")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="configurations_agents")
    niveau_automatisation = models.CharField(
        max_length=12, choices=NiveauAutomatisation.CHOIX, null=True, blank=True
    )
    niveau_gamification = models.CharField(max_length=10, choices=NiveauGamification.CHOIX, null=True, blank=True)
    fonctions_desactivees = models.JSONField(default=list, blank=True)
    prefere_vocal = models.BooleanField(null=True, blank=True)
    prefere_vocal_impose = models.BooleanField(default=False)  # voir `ConfigurationPoste.prefere_vocal_impose`
    aisance_numerique = models.CharField(
        max_length=10, choices=AisanceNumerique.CHOIX, default=AisanceNumerique.MOYENNE
    )
    modifie_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "configuration d'un agent"
        verbose_name_plural = "configurations des agents"

    def __str__(self):
        return f"Configuration de {self.agent}"


class PreferencePersonnelle(models.Model):
    """Ce que l'agent règle lui-même (« Mes paramètres ») : son mode vocal, sauf si son supérieur l'a imposé, et la façon
    d'être prévenu d'une alerte critique sur le site (son, notification du navigateur). Rien de réglé : comme avant."""

    agent = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preference_personnelle")
    prefere_vocal = models.BooleanField(null=True, blank=True)  # vide : comme réglé par son supérieur
    son_alertes = models.BooleanField(default=False)
    notifications_navigateur = models.BooleanField(default=False)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "préférences personnelles"
        verbose_name_plural = "préférences personnelles"

    def __str__(self):
        return f"Préférences de {self.agent}"
