from django.contrib import admin

from reseau.models import Gare, Ligne, Quai, Vehicule


@admin.register(Gare)
class GareAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "company", "chef", "telephone"]
    list_filter = ["company"]
    search_fields = ["nom", "ville"]


@admin.register(Quai)
class QuaiAdmin(admin.ModelAdmin):
    list_display = ["nom", "gare", "company", "actif"]
    list_filter = ["company", "actif"]


@admin.register(Ligne)
class LigneAdmin(admin.ModelAdmin):
    list_display = ["nom", "gare_depart", "gare_arrivee", "tarif", "company"]
    list_filter = ["company"]


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ["immatriculation", "marque", "modele", "annee_mise_en_circulation", "capacite", "statut", "company"]
    list_filter = ["company", "statut", "classe"]
    search_fields = ["immatriculation"]
