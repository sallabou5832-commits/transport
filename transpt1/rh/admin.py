from django.contrib import admin

from rh import models


class _LectureSeule(admin.ModelAdmin):
    """Lecture seule : la RH se tient par l'API (alertes, trace d'audit, règles de visibilité), jamais à la main."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for modele in (
    models.ObligationFormation, models.FormationSuivie, models.ContratAgent, models.EvaluationAgent, models.MesureDisciplinaire,
    models.DemandeConge, models.FicheDePoste, models.OffreRecrutement, models.Candidature, models.Doleance, models.SuiviDoleance,
):
    admin.site.register(modele, _LectureSeule)
