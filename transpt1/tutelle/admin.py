from django.contrib import admin

from tutelle.models import CompteTutelle, FluxTutelle


@admin.register(FluxTutelle)
class FluxTutelleAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "type", "direction", "statut", "date"]
    list_filter = ["type", "direction", "statut", "company"]
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False  # les flux se génèrent automatiquement, ou arrivent de la tutelle par l'API


@admin.register(CompteTutelle)
class CompteTutelleAdmin(admin.ModelAdmin):
    list_display = ["id", "nom", "actif", "cree_le", "derniere_utilisation"]
    readonly_fields = ["cle_hachee", "cree_le", "derniere_utilisation"]

    def has_add_permission(self, request):
        return False  # la clé ne s'affiche qu'une fois, à la création : voir `manage.py creer_compte_tutelle`
