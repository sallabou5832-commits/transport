from django.contrib import admin

from reseau.models import Gare, Ligne, Vehicule


@admin.register(Gare)
class GareAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "company", "chef"]
    list_filter = ["company"]
    search_fields = ["nom", "ville"]


@admin.register(Ligne)
class LigneAdmin(admin.ModelAdmin):
    list_display = ["nom", "gare_depart", "gare_arrivee", "company"]
    list_filter = ["company"]


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ["immatriculation", "capacite", "statut", "company"]
    list_filter = ["company", "statut"]
    search_fields = ["immatriculation"]
