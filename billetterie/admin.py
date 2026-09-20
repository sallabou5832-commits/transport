from django.contrib import admin

from billetterie.models import Depart, Ticket


@admin.register(Depart)
class DepartAdmin(admin.ModelAdmin):
    list_display = ["ligne", "vehicule", "chauffeur", "date_heure", "statut", "places_vendues", "company"]
    list_filter = ["company", "statut"]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["depart", "passager_nom", "prix", "mode_paiement", "vendu_par", "date_vente", "company"]
    list_filter = ["company", "mode_paiement"]
    search_fields = ["passager_nom", "passager_telephone"]
