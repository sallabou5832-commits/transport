from django.db import models
from django.utils import timezone

from core.models import Company, User


class MissionAccomplie(models.Model):
    """Une mission du jour accomplie par un agent : enregistrée une seule fois (elle rapporte des points), et
    conservée pour l'historique. Le score, lui, n'est pas stocké : il se recalcule à partir de ce que l'agent a fait."""

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="missions_accomplies")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="+")
    code = models.CharField(max_length=40)
    date = models.DateField()
    accomplie_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "mission accomplie"
        verbose_name_plural = "missions accomplies"
        constraints = [models.UniqueConstraint(fields=["agent", "code", "date"], name="une_mission_par_jour_et_par_agent")]
        indexes = [models.Index(fields=["agent", "date"], name="mission_agent_date")]

    def __str__(self):
        return f"{self.agent} : {self.code} ({self.date})"


class BadgeObtenu(models.Model):
    """Un badge remporté. `periode` distingue les badges qui se regagnent (« Gare du mois » : « 2026-09 ») ; vide pour
    ceux qu'on n'obtient qu'une fois."""

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="+")
    code = models.CharField(max_length=40)
    periode = models.CharField(max_length=10, blank=True)
    obtenu_le = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "badge obtenu"
        verbose_name_plural = "badges obtenus"
        constraints = [models.UniqueConstraint(fields=["agent", "code", "periode"], name="un_badge_par_periode_et_par_agent")]

    def __str__(self):
        return f"{self.agent} : {self.code} {self.periode}".strip()
