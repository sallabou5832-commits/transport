from django.contrib import admin

from alertes.models import Alerte


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = ["cree_le", "company", "gravite", "type", "titre"]
    list_filter = ["company", "gravite", "type"]
    search_fields = ["titre", "message"]
    readonly_fields = ["cree_le", "cle"]
