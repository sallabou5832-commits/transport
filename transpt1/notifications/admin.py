from django.contrib import admin

from notifications.models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["destinataire", "canal", "statut", "date_envoi", "ticket", "colis", "company"]
    list_filter = ["company", "canal", "statut"]
    search_fields = ["destinataire", "contenu"]
