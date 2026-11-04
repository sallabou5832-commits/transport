from django.contrib import admin

from maintenance.models import EntreePiece, InventairePiece, OrdreReparation, Piece, SortiePiece


@admin.register(Piece)
class PieceAdmin(admin.ModelAdmin):
    list_display = ["nom", "reference", "quantite_stock", "seuil_alerte", "prix_unitaire", "emplacement", "company"]
    list_filter = ["company"]
    search_fields = ["nom", "reference"]


@admin.register(OrdreReparation)
class OrdreReparationAdmin(admin.ModelAdmin):
    list_display = ["id", "vehicule", "statut", "mecanicien", "date_creation", "date_cloture", "company"]
    list_filter = ["company", "statut"]


@admin.register(SortiePiece)
class SortiePieceAdmin(admin.ModelAdmin):
    list_display = ["ordre_reparation", "piece", "quantite", "date", "company"]
    list_filter = ["company"]


@admin.register(EntreePiece)
class EntreePieceAdmin(admin.ModelAdmin):
    list_display = ["piece", "quantite", "prix_unitaire", "fournisseur", "reference_document", "recue_par", "date", "company"]
    list_filter = ["company"]


@admin.register(InventairePiece)
class InventairePieceAdmin(admin.ModelAdmin):
    list_display = ["piece", "quantite_attendue", "quantite_comptee", "motif", "compte_par", "date", "company"]
    list_filter = ["company"]
