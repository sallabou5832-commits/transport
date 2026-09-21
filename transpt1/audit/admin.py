from django.contrib import admin

from audit.models import JournalAudit


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    """Lecture seule : ni ajout, ni modification, ni suppression, pas même pour un superadmin."""

    list_display = ["date", "acteur_nom", "acteur_role", "action", "objet_type", "objet_repr", "company", "adresse_ip"]
    list_filter = ["action", "objet_type", "company", "acteur_role"]
    search_fields = ["acteur_nom", "objet_repr", "objet_id"]
    date_hierarchy = "date"
    readonly_fields = [f.name for f in JournalAudit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
