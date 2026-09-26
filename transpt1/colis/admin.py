from django.contrib import admin

from colis.models import Colis


@admin.register(Colis)
class ColisAdmin(admin.ModelAdmin):
    """Lecture seule : un colis se suit par ses étapes, jamais par une modification à la main (et l'empreinte du code
    de retrait n'a rien à faire à l'écran)."""

    list_display = ["id", "description", "statut", "depart", "destinataire_nom", "company"]
    list_filter = ["company", "statut", "type_colis"]
    search_fields = ["description", "expediteur_nom", "destinataire_nom"]
    exclude = ["code_retrait_hash"]
    readonly_fields = [f.name for f in Colis._meta.fields if f.name != "code_retrait_hash"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
