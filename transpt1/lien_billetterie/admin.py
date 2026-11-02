from django.contrib import admin

from lien_billetterie.models import CleLienBilletterie, ImportVentes, ReglageBilletterie


@admin.register(ReglageBilletterie)
class ReglageBilletterieAdmin(admin.ModelAdmin):
    list_display = ["company", "mode", "modifie_par", "modifie_le"]
    list_filter = ["mode"]


@admin.register(CleLienBilletterie)
class CleLienBilletterieAdmin(admin.ModelAdmin):
    list_display = ["logiciel", "company", "debut_cle", "active", "creee_le", "derniere_utilisation"]
    list_filter = ["company", "active"]
    # La clé se crée par l'API (seule à la montrer en clair) ; l'administration ne fait que la consulter.
    readonly_fields = ["company", "logiciel", "debut_cle", "creee_par", "creee_le", "revoquee_par", "revoquee_le", "derniere_utilisation"]

    def has_add_permission(self, request):
        return False


@admin.register(ImportVentes)
class ImportVentesAdmin(admin.ModelAdmin):
    list_display = ["fichier", "logiciel", "company", "depose_par", "depose_le", "creees", "deja_recues", "refusees"]
    list_filter = ["company"]
