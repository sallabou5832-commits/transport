from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Journal d'audit"

    def ready(self):
        from audit import signals  # noqa: F401  (branche l'enregistrement automatique)

        signals.brancher()
