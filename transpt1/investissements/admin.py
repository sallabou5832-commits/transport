from django.contrib import admin

from investissements.models import Investissement


@admin.register(Investissement)
class InvestissementAdmin(admin.ModelAdmin):
    """Lecture seule : une demande se décide par l'API (avec son motif, ses alertes et sa trace), jamais à la main."""

    list_display = ["id", "libelle", "type", "montant", "statut", "demandeur", "company"]
    list_filter = ["company", "statut", "type"]
    search_fields = ["libelle"]
    readonly_fields = [f.name for f in Investissement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
