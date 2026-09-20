from django.contrib import admin

from personnel_roulant.models import ChecklistDepart, FeuilleDeRoute, Incident


@admin.register(FeuilleDeRoute)
class FeuilleDeRouteAdmin(admin.ModelAdmin):
    list_display = ["depart", "chauffeur", "heure_depart_prevue", "heure_depart_reelle", "company"]
    list_filter = ["company"]


@admin.register(ChecklistDepart)
class ChecklistDepartAdmin(admin.ModelAdmin):
    list_display = ["feuille_de_route", "item", "etat", "company"]
    list_filter = ["company", "etat"]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["type_incident", "vehicule", "chauffeur", "gravite", "statut", "date", "company"]
    list_filter = ["company", "type_incident", "gravite", "statut"]
