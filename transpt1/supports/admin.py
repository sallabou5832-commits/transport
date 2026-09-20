from django.contrib import admin

from supports.models import Assurance, DossierAgent, Sinistre


@admin.register(DossierAgent)
class DossierAgentAdmin(admin.ModelAdmin):
    list_display = ["agent", "poste", "statut", "date_embauche", "company"]
    list_filter = ["company", "statut"]


@admin.register(Assurance)
class AssuranceAdmin(admin.ModelAdmin):
    list_display = ["vehicule", "compagnie_assurance", "numero_police", "date_echeance", "company"]
    list_filter = ["company"]


@admin.register(Sinistre)
class SinistreAdmin(admin.ModelAdmin):
    list_display = ["id", "vehicule", "incident", "statut", "date", "company"]
    list_filter = ["company", "statut"]
