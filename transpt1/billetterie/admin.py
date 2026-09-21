from django.contrib import admin

from billetterie.models import Depart, Ticket


@admin.register(Depart)
class DepartAdmin(admin.ModelAdmin):
    list_display = ["ligne", "vehicule", "chauffeur", "date_heure", "statut", "places_vendues", "company"]
    list_filter = ["company", "statut"]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """Consultation seulement : un ticket vendu est une pièce de caisse, il ne s'ajoute, ne se modifie et ne se
    supprime pas dans l'administration (pas même par un superadmin). Une erreur passe par l'annulation tracée."""

    list_display = ["depart", "passager_nom", "prix", "mode_paiement", "statut", "vendu_par", "date_vente", "company"]
    list_filter = ["company", "statut", "mode_paiement"]
    search_fields = ["passager_nom", "passager_telephone"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
